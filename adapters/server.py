from __future__ import annotations

import os
import shutil
from pathlib import Path
from uuid import uuid4

import uvicorn
import yaml
from fastapi import FastAPI, File, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from adapters.cli import create_agent
from core.llm import PROVIDERS
from data.seed_sample_db import ensure_sample_db
import logging
from core.logger import setup_logging

logger = logging.getLogger(__name__)


class ChatRequest(BaseModel):
    text: str
    image_paths: list[str] = []
    provider: str = "kimi"


def build_app() -> FastAPI:
    app = FastAPI()

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
        steps: list[dict] = []
        logger.info(f"/api/chat 请求: provider={payload.provider}, text={payload.text[:200]}, images={payload.image_paths}")
        agent = create_agent(payload.provider)
        reply = agent.run(payload.text, payload.image_paths, steps.append)
        return {"reply": reply, "steps": steps}

    @app.post("/api/upload")
    def upload(file: UploadFile = File(...)):
        upload_dir = Path("uploads")
        upload_dir.mkdir(parents=True, exist_ok=True)
        save_path = upload_dir / f"{uuid4().hex}{Path(file.filename or '').suffix}"
        with save_path.open("wb") as target:
            shutil.copyfileobj(file.file, target)
        path = f"{save_path.as_posix()}"
        logger.info(f"文件上传: saved to {path}")
        return {"path": path}

    return app


def run_server() -> None:
    # 初始化日志
    setup_logging()
    ensure_sample_db(Path("data") / "sample.db")
    with Path("config.yaml").open("r", encoding="utf-8") as file:
        config = yaml.safe_load(file) or {}
    webui_config = config.get("webui", {})
    uvicorn.run(build_app(), host=webui_config.get("host", "127.0.0.1"), port=webui_config.get("port", 8000))
