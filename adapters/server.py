from __future__ import annotations

import re
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from core.runtime import build_agent, get_project_root, get_provider_statuses, load_config, setup_logging


class ChatRequest(BaseModel):
    text: str = Field(min_length=1)
    image_paths: list[str] = Field(default_factory=list)
    provider: str | None = None
    model: str | None = None


class ChatResponse(BaseModel):
    reply: str
    steps: list[dict]


def create_app(config_path: str = "config.yaml") -> FastAPI:
    root = get_project_root()
    config = load_config(config_path)
    setup_logging(config.get("logging", {}).get("level", "INFO"))

    app = FastAPI(title="Mini Agent", version="0.1.0")
    app.mount("/uploads", StaticFiles(directory=str(root / "uploads")), name="uploads")

    @app.get("/")
    def index():
        return FileResponse(root / "webui" / "index.html")

    @app.get("/api/providers")
    def providers():
        return get_provider_statuses()

    @app.post("/api/upload")
    def upload(file: UploadFile = File(...)):
        uploads_dir = root / "uploads"
        uploads_dir.mkdir(parents=True, exist_ok=True)
        safe_name = re.sub(r"[^a-zA-Z0-9._-]", "_", file.filename or "upload.bin")
        target = uploads_dir / f"{uuid4().hex}_{safe_name}"
        data = file.file.read()
        target.write_bytes(data)
        return {"path": f"/uploads/{target.name}"}

    @app.post("/api/chat", response_model=ChatResponse)
    def chat(req: ChatRequest):
        try:
            active_config = load_config(config_path)
            agent = build_agent(active_config, provider_override=req.provider, model_override=req.model)
            steps: list[dict] = []
            resolved_image_paths = [_resolve_image_path(root, p) for p in req.image_paths]
            reply = agent.run(req.text, resolved_image_paths, on_step=lambda s: steps.append(s))
            return ChatResponse(reply=reply, steps=steps)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    return app


def _resolve_image_path(root: Path, path: str) -> str:
    # Web upload API returns "/uploads/<file>", convert it to local absolute path for the agent runtime.
    if path.startswith("/uploads/"):
        return str((root / "uploads" / path.removeprefix("/uploads/")).resolve())
    p = Path(path)
    if p.is_absolute():
        return str(p)
    return str((root / path).resolve())
