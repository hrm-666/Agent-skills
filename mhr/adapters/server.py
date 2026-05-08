from __future__ import annotations

import json
import os
import logging
import queue
import shutil
import threading
import time
from pathlib import Path
from uuid import uuid4

import uvicorn
import yaml
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from adapters.cli import create_agent
from core.agent import AgentConfirmationRequired
from core.llm import PROVIDERS

logger = logging.getLogger(__name__)


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


class ChatRequest(BaseModel):
    text: str
    image_paths: list[str] = []
    provider: str = "kimi"


class ConfirmRequest(BaseModel):
    confirmation_id: str


def build_app() -> FastAPI:
    load_dotenv()
    app = FastAPI()
    pending_confirmations: dict[str, dict] = {}
    Path("uploads").mkdir(parents=True, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

    def normalize_chat_text(text: str, image_paths: list[str]) -> str:
        clean_text = text.strip()
        if not clean_text and image_paths:
            files = "\n".join(f"- {path}" for path in image_paths)
            clean_text = f"用户上传了以下文件，请根据这些文件和可用技能处理：\n{files}"
        if not clean_text:
            raise HTTPException(status_code=400, detail="消息内容不能为空")
        return clean_text

    def create_confirmation(provider: str, exc: AgentConfirmationRequired) -> dict:
        confirmation_id = uuid4().hex
        pending_confirmations[confirmation_id] = {
            "provider": provider,
            "tool_name": exc.tool_name,
            "arguments": exc.arguments,
        }
        return {
            "confirmation_id": confirmation_id,
            "tool": exc.tool_name,
            "args": exc.arguments,
            "message": exc.message,
            "risk": exc.risk,
        }

    @app.get("/")
    def index():
        response = FileResponse(Path("webui") / "index.html")
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/api/providers")
    def providers():
        return [
            {
                "name": name,
                "supports_vision": meta["supports_vision"],
                "configured": bool(os.getenv(meta["env_key"])),
            }
            for name, meta in PROVIDERS.items()
        ]

    @app.post("/api/chat")
    def chat(payload: ChatRequest):
        text = normalize_chat_text(payload.text, payload.image_paths)

        steps: list[dict] = []
        logger.info(
            "chat request provider=%s text_len=%s files=%s",
            payload.provider,
            len(text),
            len(payload.image_paths),
        )
        agent = create_agent(payload.provider)
        try:
            reply = agent.run(text, payload.image_paths, steps.append)
        except AgentConfirmationRequired as exc:
            confirmation = create_confirmation(payload.provider, exc)
            logger.info("chat confirmation required provider=%s tool=%s", payload.provider, exc.tool_name)
            return {"status": "confirmation_required", "confirmation": confirmation, "steps": steps}
        logger.info("chat response provider=%s steps=%s reply_len=%s", payload.provider, len(steps), len(reply))
        return {"reply": reply, "steps": steps}

    @app.post("/api/chat/stream")
    def chat_stream(payload: ChatRequest):
        text = normalize_chat_text(payload.text, payload.image_paths)

        logger.info(
            "chat stream request provider=%s text_len=%s files=%s",
            payload.provider,
            len(text),
            len(payload.image_paths),
        )

        def event_stream():
            events: queue.Queue[tuple[str, dict] | None] = queue.Queue()
            run_done = threading.Event()
            progress_path = Path("workspace") / "pledgebox-order-output" / "progress.json"

            def run_agent():
                steps: list[dict] = []
                try:
                    agent = create_agent(payload.provider)
                    events.put(("agent_start", {"provider": payload.provider, "text": text}))

                    def on_step(step: dict) -> None:
                        steps.append(step)
                        events.put(("tool_result", step))

                    def on_text_delta(delta: str) -> None:
                        events.put(("assistant_delta", {"text": delta}))

                    reply = agent.run(text, payload.image_paths, on_step, on_text_delta)
                    logger.info(
                        "chat stream response provider=%s steps=%s reply_len=%s",
                        payload.provider,
                        len(steps),
                        len(reply),
                    )
                    events.put(("agent_done", {"reply": reply, "steps_count": len(steps)}))
                except AgentConfirmationRequired as exc:
                    confirmation = create_confirmation(payload.provider, exc)
                    logger.info("chat stream confirmation required provider=%s tool=%s", payload.provider, exc.tool_name)
                    events.put(("confirmation_required", confirmation))
                except Exception as exc:
                    logger.exception("chat stream failed provider=%s", payload.provider)
                    events.put(("agent_error", {"error": str(exc)}))
                finally:
                    run_done.set()
                    events.put(None)

            def watch_progress():
                last_text = None
                while not run_done.is_set():
                    try:
                        if progress_path.exists():
                            text = progress_path.read_text(encoding="utf-8")
                            if text and text != last_text:
                                last_text = text
                                events.put(("progress_update", json.loads(text)))
                    except Exception:
                        logger.exception("progress watcher failed")
                    time.sleep(0.5)

            threading.Thread(target=run_agent, daemon=True).start()
            threading.Thread(target=watch_progress, daemon=True).start()

            while True:
                item = events.get()
                if item is None:
                    break
                event, data = item
                yield _sse(event, data)

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    @app.post("/api/tool/confirm")
    def confirm_tool(payload: ConfirmRequest):
        item = pending_confirmations.pop(payload.confirmation_id, None)
        if not item:
            raise HTTPException(status_code=404, detail="待确认操作不存在或已失效")

        logger.info("tool confirmation accepted provider=%s tool=%s", item["provider"], item["tool_name"])
        agent = create_agent(item["provider"])
        result = agent.tool_registry.execute(item["tool_name"], item["arguments"], confirmed=True)
        return {
            "tool": item["tool_name"],
            "args": item["arguments"],
            "result": result,
        }

    @app.post("/api/upload")
    def upload(file: UploadFile = File(...)):
        upload_dir = Path("uploads")
        upload_dir.mkdir(parents=True, exist_ok=True)
        save_path = upload_dir / f"{uuid4().hex}{Path(file.filename or '').suffix}"
        with save_path.open("wb") as target:
            shutil.copyfileobj(file.file, target)
        logger.info("uploaded file original=%s saved=%s", file.filename, save_path)
        return {"path": f"/{save_path.as_posix()}"}

    return app


def run_server() -> None:
    with Path("config.yaml").open("r", encoding="utf-8") as file:
        config = yaml.safe_load(file) or {}
    webui_config = config.get("webui", {})
    uvicorn.run(build_app(), host=webui_config.get("host", "127.0.0.1"), port=webui_config.get("port", 8000))
