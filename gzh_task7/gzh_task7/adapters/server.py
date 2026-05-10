"""
FastAPI 服务器 - WebUI 后端
"""
import os
import json
import logging
import shutil
from pathlib import Path
from typing import Optional, List, Dict
from datetime import datetime

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse
from pydantic import BaseModel
from rich.console import Console

from core.llm import LLM
from core.skills import SkillLoader
from core.tools import ToolRegistry
from core.agent import Agent
from core.memory import get_memory, set_memory_mode, clear_memory

console = Console()
logger = logging.getLogger(__name__)

_llm: Optional[LLM] = None
_skill_loader: Optional[SkillLoader] = None
_max_iterations: int = 15


def init(llm: LLM, skill_loader: SkillLoader, max_iterations: int):
    """初始化全局依赖"""
    global _llm, _skill_loader, _max_iterations
    _llm = llm
    _skill_loader = skill_loader
    _max_iterations = max_iterations


app = FastAPI(title="Mini Agent", description="遵循 agentskills.io 标准的智能体")

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


class ChatRequest(BaseModel):
    text: str
    image_paths: Optional[List[str]] = None
    file_paths: Optional[List[str]] = None
    provider: Optional[str] = None


class ToolStep(BaseModel):
    type: str
    name: Optional[str] = None
    args: Optional[dict] = None
    result: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str
    steps: List[ToolStep] = []


class ProviderInfo(BaseModel):
    name: str
    supports_vision: bool
    configured: bool


class MemoryConfigRequest(BaseModel):
    mode: str
    limit: Optional[int] = 10


class MemoryInfoResponse(BaseModel):
    mode: str
    limit: Optional[int]
    count: int
    history: List[Dict] = []


@app.get("/")
def root():
    html_path = Path(__file__).parent.parent / "webui" / "index.html"
    if html_path.exists():
        return HTMLResponse(content=html_path.read_text(encoding='utf-8'))
    raise HTTPException(status_code=404, detail="WebUI not found")


@app.get("/api/providers")
def get_providers():
    env_key_map = {
        "kimi": "MOONSHOT_API_KEY",
        "qwen": "DASHSCOPE_API_KEY",
        "deepseek": "DEEPSEEK_API_KEY",
    }
    
    providers = []
    for name in ["kimi", "qwen", "deepseek"]:
        providers.append(ProviderInfo(
            name=name,
            supports_vision=(name != "deepseek"),
            configured=bool(os.getenv(env_key_map[name]))
        ))
    return providers


@app.post("/api/upload")
def upload_file(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename")
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = f"{timestamp}_{file.filename}"
    file_path = UPLOAD_DIR / safe_name
    
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    
    return {
        "path": str(file_path),
        "url": f"/uploads/{safe_name}",
        "name": file.filename,
        "size": file_path.stat().st_size
    }


@app.post("/api/chat")
def chat(request: ChatRequest):
    global _llm, _skill_loader, _max_iterations
    
    if _llm is None:
        raise HTTPException(status_code=500, detail="LLM not initialized")
    
    steps: List[ToolStep] = []
    
    user_text = request.text
    
    if request.file_paths:
        file_context = "\n\n[已上传的文件]\n"
        for file_url in request.file_paths:
            file_name = file_url.split("/")[-1]
            is_image = file_url.endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp'))
            if is_image:
                file_context += f"- 图片: {file_url} (可通过视觉能力分析)\n"
            else:
                file_context += f"- 文件: {file_url} (可通过 read 工具读取，或用 bash 工具处理)\n"
        file_context += "\n你可以使用 read、bash 或 视觉能力 来处理这些文件。"
        user_text = request.text + file_context
    
    def on_step(step):
        if step["type"] == "tool_call":
            steps.append(ToolStep(
                type="tool_call",
                name=step["name"],
                args=step["args"]
            ))
        elif step["type"] == "tool_result":
            for s in reversed(steps):
                if s.type == "tool_call" and s.result is None:
                    s.result = step["result"][:500]
                    break
    
    try:
        tool_registry = ToolRegistry()
        agent = Agent(_llm, _skill_loader, tool_registry, _max_iterations)
        answer = agent.run(user_text, request.image_paths, on_step)
        return ChatResponse(reply=answer, steps=steps)
    except Exception as e:
        logger.exception("Chat error")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/chat/stream")
async def chat_stream(request: ChatRequest):
    global _llm, _skill_loader, _max_iterations
    
    if _llm is None:
        raise HTTPException(status_code=500, detail="LLM not initialized")
    
    user_text = request.text
    
    if request.file_paths:
        file_context = "\n\n[已上传的文件]\n"
        for file_url in request.file_paths:
            file_name = file_url.split("/")[-1]
            is_image = file_url.endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp'))
            if is_image:
                file_context += f"- 图片: {file_url}\n"
            else:
                file_context += f"- 文件: {file_url}\n"
        user_text = request.text + file_context
    
    async def generate():
        try:
            tool_registry = ToolRegistry()
            agent = Agent(_llm, _skill_loader, tool_registry, _max_iterations)
            
            steps = []
            
            for event in agent.run_stream(user_text, request.image_paths):
                if event["type"] == "tool_call":
                    steps.append({"type": "tool_call", "name": event["name"], "args": event["args"], "result": None})
                    yield f"data: {json.dumps({'type': 'tool_call', 'name': event['name'], 'args': event['args']})}\n\n"
                    
                elif event["type"] == "tool_result":
                    for s in steps:
                        if s.get("name") == event["name"] and s.get("result") is None:
                            s["result"] = event["result"][:500]
                            break
                    yield f"data: {json.dumps({'type': 'tool_result', 'name': event['name'], 'result': event['result'][:500]})}\n\n"
                    
                elif event["type"] == "chunk":
                    yield f"data: {json.dumps({'type': 'chunk', 'content': event['content']})}\n\n"
                    
                elif event["type"] == "complete":
                    yield f"data: {json.dumps({'type': 'complete', 'content': event['content'], 'steps': steps})}\n\n"
                    
                elif event["type"] == "error":
                    yield f"data: {json.dumps({'type': 'error', 'content': event['content']})}\n\n"
            
            yield "data: [DONE]\n\n"
            
        except Exception as e:
            logger.exception("Stream chat error")
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
    
    return StreamingResponse(
        generate(), 
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@app.get("/uploads/{filename}")
def serve_upload(filename: str):
    file_path = UPLOAD_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path)


# ========== 记忆管理 API ==========

@app.get("/api/memory/info")
def get_memory_info():
    """获取当前记忆状态"""
    memory = get_memory()
    info = memory.get_info()
    return MemoryInfoResponse(
        mode=info["mode"],
        limit=info.get("limit"),
        count=info["count"],
        history=info.get("history", [])
    )


@app.post("/api/memory/config")
def set_memory_config(request: MemoryConfigRequest):
    """设置记忆模式"""
    try:
        set_memory_mode(request.mode, request.limit or 10)
        return {"success": True, "message": f"记忆模式已设置为 {request.mode}"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/memory/clear")
def clear_memory_history():
    """清空记忆"""
    clear_memory()
    return {"success": True, "message": "记忆已清空"}