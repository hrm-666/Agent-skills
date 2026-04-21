"""FastAPI server for mini-agent WebUI."""

import json
import logging
import os
from pathlib import Path
from typing import Optional

import yaml
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from core.agent import Agent
from core.llm import LLM, PROVIDERS, ProviderName
from core.skills import SkillLoader
from core.tools import ToolRegistry
from tools_builtin.file_ops import read_tool, write_tool
from tools_builtin.shell import bash_tool
from tools_builtin.skill_ops import activate_skill_tool

logger = logging.getLogger(__name__)

# Load config
CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"
with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    cfg = yaml.safe_load(f)

# Paths
UPLOADS_DIR = Path("uploads")
UPLOADS_DIR.mkdir(exist_ok=True)

# Initialize skill loader
skills_dir = Path(cfg["skills"]["dir"])
skill_loader = SkillLoader(skills_dir, enabled=cfg["skills"].get("enabled"))
skill_loader.scan()

# Initialize tool registry
tool_registry = ToolRegistry()
tool_registry.register(*read_tool())
tool_registry.register(*write_tool())
tool_registry.register(*bash_tool())
tool_registry.register(*activate_skill_tool(skill_loader))

# Build system prompt for agent
def build_system_prompt() -> str:
    skill_catalog = skill_loader.get_catalog_text()
    return f"""You are a task execution agent that uses tools and skills to help users.

  You have 4 built-in tools: read, write, bash, activate_skill.

  IMPORTANT: Before executing any specialized task, check if there's a relevant skill in the catalog below. If yes, use
  activate_skill(name) to load its full instructions. Don't guess — skills contain the exact commands and schemas you
  need.

  {skill_catalog}

  Rules:
  - Always use activate_skill BEFORE bash-ing into a skill's scripts
  - After activating a skill, follow its SKILL.md instructions exactly
  - Keep responses concise unless user asks for detail"""


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
    active_provider = cfg.get("active_provider", "kimi")
    providers = []
    for name, config in PROVIDERS.items():
        api_key = os.environ.get(config["env_key"], "")
        providers.append({
            "name": name,
            "base_url": config["base_url"],
            "default_model": config["default_model"],
            "supports_vision": config["supports_vision"],
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
    text = request.text
    provider = request.provider
    image_paths = request.image_paths

    if not text or not text.strip():
        raise HTTPException(status_code=400, detail="text is required and cannot be empty")

    # Use active provider from config or override
    active_provider = provider or cfg["active_provider"]
    if active_provider not in PROVIDERS:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {active_provider}")

    env_key = PROVIDERS[active_provider]["env_key"]
    api_key = os.environ.get(env_key)
    if not api_key:
        raise HTTPException(status_code=400, detail=f"API key not configured for {active_provider} (env: {env_key})")

    # Initialize LLM
    llm = LLM(provider=active_provider, api_key=api_key)

    # Build agent components
    system_prompt = build_system_prompt()
    tools = tool_registry.get_openai_schemas()

    # Prepare messages
    if image_paths:
        content = [
            {"type": "text", "text": text},
            *[
                {"type": "image_url", "image_url": {"url": path}}
                for path in image_paths
            ]
        ]
    else:
        content = text

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": content}
    ]

    max_iterations = cfg["agent"]["max_iterations"]
    steps = []
    reply = ""

    for iteration in range(max_iterations):
        response = llm.complete(
            system=system_prompt,
            messages=messages,
            tools=tools if tools else None
        )

        if response.tool_calls:
            assistant_msg = {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    }
                    for tc in response.tool_calls
                ],
                "reasoning_content": response.reasoning_content
            }
            messages.append(assistant_msg)

            for tc in response.tool_calls:
                args = json.loads(tc.function.arguments)
                result = tool_registry.execute(tc.function.name, args)
                steps.append({
                    "type": "tool_call",
                    "name": tc.function.name,
                    "arguments": str(args),
                    "result": result,
                })
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result,
                })
            continue

        if response.content is not None:
            reply = response.content
            break

        # If no content and no tool calls, return what we have
        reply = response.content or "No response"
        break

    if not reply:
        reply = "Error: Exceeded maximum iterations."

    return ChatResponse(reply=reply, steps=steps)


@app.post("/api/upload")
def upload_file(file: UploadFile = File(...)):
    """Upload a file to the uploads directory."""
    file_path = UPLOADS_DIR / file.filename
    with open(file_path, "wb") as f:
        content = file.file.read()
        f.write(content)
    return {"filename": file.filename, "path": f"/uploads/{file.filename}"}