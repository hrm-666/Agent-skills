"""FastAPI server for mini-agent WebUI."""

import os
import logging
import uvicorn
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
from pydantic import BaseModel
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI, HTTPException, UploadFile, File

load_dotenv()

from core.agent import Agent
from core.utils import load_config
from core.tools import register_tools
from core.skills import get_skill_loader
from core.llm import LLM, PROVIDERS,LLMResponse

logger = logging.getLogger(__name__)
config = load_config()
UPLOADS_DIR = Path("uploads")
UPLOADS_DIR.mkdir(exist_ok=True)

# Request/Response models
class ChatRequest(BaseModel):
    text: str
    provider: Optional[str] = None
    image_paths: Optional[list[str]] = None

class ChatResponse(BaseModel):
    reply: str
    steps: list[dict]


# FastAPI app
app = FastAPI(title="mini-agent WebUI")

# Mount uploads directory
app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")


@app.get("/")
def root():
    """Serve the WebUI HTML page."""
    return FileResponse("webui/index.html")


@app.get("/api/providers")
def list_providers():
    """List available LLM providers with configuration status."""
    active_provider = config.get("active_provider", "deepseek")
    providers = []
    for name, provider_config in PROVIDERS.items():
        api_key = os.environ.get(provider_config["env_key"], "")
        providers.append({
            "name": name,
            "base_url": provider_config["base_url"],
            "default_model": provider_config["default_model"],
            "supports_vision": provider_config["supports_vision"],
            "configured": bool(api_key),
            "active": name == active_provider,
        })
    return providers


@app.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    """
    Chat endpoint that replicates the agent loop inline to capture each step.
    Returns the final reply and a list of tool call steps.
    """
    user_text = request.text
    provider = request.provider
    image_paths = request.image_paths

    if not user_text or not user_text.strip():
        raise HTTPException(status_code=400, detail="text is required and cannot be empty")

    active_provider = provider or config.get("active_provider", "kimi")
    active_provider_cfg = PROVIDERS[active_provider]

    if active_provider not in PROVIDERS:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {active_provider}")

    api_key = os.environ.get(active_provider_cfg["env_key"])
    if not api_key:
        raise HTTPException(status_code=400, detail=f"API key not configured for {active_provider}")

    llm = LLM(provider=active_provider, api_key=api_key)
    max_iter = config.get("agent", {}).get("max_iterations", 15)

    steps = []

    def onstep(iteration, response: "LLMResponse") -> None:
        if response.tool_calls:
            for tool_call in response.tool_calls:
                steps.append({
                    "name": tool_call.function.name,
                    "arguments": tool_call.function.arguments,
                })

    reply = Agent(llm,get_skill_loader(),register_tools(),max_iter).run(user_text, image_paths, onstep)

    return ChatResponse(reply=reply, steps=steps)


@app.post("/api/upload")
def upload_file(file: UploadFile = File(...)):
    """Upload a file to the uploads directory."""
    file_path = UPLOADS_DIR / file.filename
    with open(file_path, "wb") as f:
        content = file.file.read()
        f.write(content)
    return {"filename": file.filename, "path": f"/uploads/{file.filename}"}

def webui_run() -> None:
    webui_cfg = config.get("webui", {})
    host = webui_cfg.get("host", "127.0.0.1")
    port = webui_cfg.get("port", 8000)
    uvicorn.run(app, host=host, port=port)