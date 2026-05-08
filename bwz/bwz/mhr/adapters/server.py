from __future__ import annotations

import os
import logging
import shutil
from pathlib import Path
from uuid import uuid4

import uvicorn
import yaml
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from adapters.cli import create_agent
from core.llm import PROVIDERS
from data.seed_sample_db import ensure_sample_db

logger = logging.getLogger(__name__)


class ChatRequest(BaseModel):
    text: str
    image_paths: list[str] = []
    provider: str = "kimi"


def build_app() -> FastAPI:
    load_dotenv()
    app = FastAPI()
    Path("uploads").mkdir(parents=True, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

    @app.get("/")
    def index():
        return FileResponse(Path("webui") / "index.html")

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
        text = payload.text.strip()
        if not text and payload.image_paths:
            files = "\n".join(f"- {path}" for path in payload.image_paths)
            text = f"用户上传了以下文件，请根据这些文件和可用技能处理：\n{files}"
        if not text:
            raise HTTPException(status_code=400, detail="消息内容不能为空")

        steps: list[dict] = []
        logger.info(
            "chat request provider=%s text_len=%s files=%s",
            payload.provider,
            len(text),
            len(payload.image_paths),
        )
        agent = create_agent(payload.provider)
        reply = agent.run(text, payload.image_paths, steps.append)
        logger.info("chat response provider=%s steps=%s reply_len=%s", payload.provider, len(steps), len(reply))
        return {"reply": reply, "steps": steps}

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
    ensure_sample_db(Path("data") / "sample.db")
    with Path("config.yaml").open("r", encoding="utf-8") as file:
        config = yaml.safe_load(file) or {}
    webui_config = config.get("webui", {})
    uvicorn.run(build_app(), host=webui_config.get("host", "127.0.0.1"), port=webui_config.get("port", 8000))
