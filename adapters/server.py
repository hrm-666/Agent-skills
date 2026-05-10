"""
FastAPI 服务：WebUI + SSE 流式 + 会话历史 + 确认机制 + 文件下载
"""
import json
import logging
import mimetypes
import os
import queue
import shutil
import threading
import uuid
from pathlib import Path

import uvicorn
import yaml
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from adapters.cli import create_agent
from core.llm import PROVIDERS
from core.logging_setup import setup_logging

logger = logging.getLogger(__name__)

UPLOADS_DIR = Path("uploads")
UPLOADS_DIR.mkdir(exist_ok=True)
MAX_HISTORY_MESSAGES = 20
MAX_HISTORY_CHARS = 80_000


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _trim_history(messages: list[dict]) -> list[dict]:
    result = list(messages)[-MAX_HISTORY_MESSAGES:]
    while result and sum(len(str(m.get("content", ""))) for m in result) > MAX_HISTORY_CHARS:
        result.pop(0)
    return result


def build_app(workspace_dir: str = "./workspace") -> FastAPI:
    app = FastAPI(title="czon Agent", version="0.2.0")
    pending_confirmations: dict[str, dict] = {}
    pending_lock = threading.Lock()
    sessions: dict[str, list[dict]] = {}
    session_lock = threading.Lock()
    workspace_root = Path(workspace_dir).resolve()
    workspace_root.mkdir(parents=True, exist_ok=True)

    def get_history(session_id: str) -> list[dict]:
        with session_lock:
            return list(sessions.get(session_id, []))

    def append_history(session_id: str, user_text: str, assistant_text: str) -> None:
        if not session_id:
            return
        with session_lock:
            history = sessions.setdefault(session_id, [])
            history.append({"role": "user", "content": user_text})
            history.append({"role": "assistant", "content": assistant_text or ""})
            sessions[session_id] = _trim_history(history)

    @app.get("/")
    def index():
        html = Path("webui") / "index.html"
        if html.exists():
            response = FileResponse(str(html))
            response.headers["Cache-Control"] = "no-store"
            return response
        return JSONResponse({"status": "czon Agent running. No WebUI found."})

    class ChatRequest(BaseModel):
        text: str
        image_paths: list[str] = Field(default_factory=list)
        provider: str = "kimi"
        session_id: str = ""

    class ConfirmRequest(BaseModel):
        confirmation_id: str

    class ResetSessionRequest(BaseModel):
        session_id: str

    @app.post("/api/chat")
    def chat(req: ChatRequest):
        logger.info(f"/api/chat: provider={req.provider}, text={req.text[:80]}")
        try:
            agent = create_agent(req.provider)
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

        steps_out = []

        def on_step(step):
            s = {"type": step["type"], "name": step["name"], "args": step.get("args"), "result": step.get("result")}
            if req.session_id:
                result = step.get("result") or {}
                error = result.get("error") if isinstance(result, dict) else None
                if error and error.get("type") == "ConfirmationRequired":
                    conf = result.setdefault("meta", {}).setdefault("confirmation", {})
                    cid = uuid.uuid4().hex
                    conf["id"] = cid
                    conf["provider"] = req.provider
                    with pending_lock:
                        pending_confirmations[cid] = {
                            "provider": req.provider,
                            "tool_name": conf.get("tool_name") or step["name"],
                            "args": conf.get("args") or step.get("args"),
                        }
            steps_out.append(s)

        try:
            reply, _ = agent.run(req.text, req.image_paths, get_history(req.session_id), on_step=on_step)
            append_history(req.session_id, req.text, reply)
        except Exception as e:
            logger.error(f"/api/chat 执行出错：{e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

        return {"reply": reply, "steps": steps_out}

    @app.post("/api/chat/stream")
    def chat_stream(req: ChatRequest):
        logger.info(f"/api/chat/stream: provider={req.provider}, text={req.text[:80]}")

        def event_gen():
            events: queue.Queue = queue.Queue()

            def run_agent():
                try:
                    agent = create_agent(req.provider)
                except Exception as e:
                    events.put(("agent_error", {"error": str(e)}))
                    return

                def on_step(step):
                    s = {"type": step["type"], "name": step["name"], "args": step.get("args"), "result": step.get("result")}
                    if req.session_id:
                        result = step.get("result") or {}
                        error = result.get("error") if isinstance(result, dict) else None
                        if error and error.get("type") == "ConfirmationRequired":
                            conf = result.setdefault("meta", {}).setdefault("confirmation", {})
                            cid = uuid.uuid4().hex
                            conf["id"] = cid
                            conf["provider"] = req.provider
                            with pending_lock:
                                pending_confirmations[cid] = {
                                    "provider": req.provider,
                                    "tool_name": conf.get("tool_name") or step["name"],
                                    "args": conf.get("args") or step.get("args"),
                                }
                        event_name = "confirmation_required" if error and error.get("type") == "ConfirmationRequired" else "tool_result"
                    else:
                        event_name = "tool_result"
                    events.put((event_name, s))

                def on_delta(text: str):
                    events.put(("assistant_delta", {"text": text}))

                try:
                    events.put(("agent_start", {"provider": req.provider, "text": req.text}))
                    reply, steps = agent.run(
                        req.text, req.image_paths, get_history(req.session_id),
                        on_step=on_step, on_delta=on_delta,
                    )
                    append_history(req.session_id, req.text, reply)
                    events.put(("agent_done", {"reply": reply, "steps_count": len(steps)}))
                except Exception as e:
                    logger.error("/api/chat/stream 执行出错：%s", e, exc_info=True)
                    events.put(("agent_error", {"error": str(e)}))
                finally:
                    events.put(None)

            threading.Thread(target=run_agent, daemon=True).start()

            while True:
                item = events.get()
                if item is None:
                    break
                event_name, data = item
                yield _sse(event_name, data)

        return StreamingResponse(event_gen(), media_type="text/event-stream")

    @app.post("/api/tool/confirm")
    def confirm_tool(req: ConfirmRequest):
        with pending_lock:
            pending = pending_confirmations.pop(req.confirmation_id, None)

        if not pending:
            raise HTTPException(status_code=404, detail="确认请求不存在或已过期")

        try:
            agent = create_agent(pending["provider"])
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

        result = agent.tool_registry.execute(
            pending["tool_name"],
            pending["args"],
            confirmed=True,
        )
        step = {
            "type": "tool_call",
            "name": pending["tool_name"],
            "args": pending["args"],
            "result": result.to_dict(),
        }
        return {"confirmation_id": req.confirmation_id, "step": step}

    @app.post("/api/session/reset")
    def reset_session(req: ResetSessionRequest):
        with session_lock:
            sessions.pop(req.session_id, None)
        return {"ok": True}

    @app.post("/api/upload")
    def upload(file: UploadFile = File(...)):
        suffix = Path(file.filename or "upload").suffix or ""
        dest = UPLOADS_DIR / f"{uuid.uuid4().hex}{suffix}"
        with dest.open("wb") as f:
            shutil.copyfileobj(file.file, f)
        logger.info(f"文件已上传：{dest}")
        mime = file.content_type or mimetypes.guess_type(str(dest))[0] or "application/octet-stream"
        return {
            "path": str(dest),
            "name": file.filename or dest.name,
            "mime": mime,
            "size": dest.stat().st_size,
        }

    @app.get("/download/{file_path:path}")
    def download_workspace_file(file_path: str):
        target = (workspace_root / file_path).resolve()
        try:
            target.relative_to(workspace_root)
        except ValueError:
            raise HTTPException(status_code=403, detail="不允许访问 workspace 外的文件")
        if not target.exists() or not target.is_file():
            raise HTTPException(status_code=404, detail="文件不存在")
        return FileResponse(str(target), filename=target.name)

    @app.get("/api/providers")
    def get_providers():
        result = []
        for name, cfg in PROVIDERS.items():
            result.append({
                "name": name,
                "supports_vision": cfg["supports_vision"],
                "configured": bool(os.getenv(cfg["env_key"], "")),
            })
        return result

    return app


def run_server() -> None:
    setup_logging()
    with Path("config.yaml").open("r", encoding="utf-8") as file:
        config = yaml.safe_load(file) or {}
    webui_config = config.get("webui", {})
    workspace_dir = config.get("workspace", {}).get("dir", "./workspace")
    app = build_app(workspace_dir=workspace_dir)
    uvicorn.run(
        app,
        host=webui_config.get("host", "127.0.0.1"),
        port=webui_config.get("port", 8000),
    )
