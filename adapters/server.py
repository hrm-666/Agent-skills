"""
FastAPI 服务器 - WebUI 后端
"""
import os
import logging
import shutil
import asyncio
from pathlib import Path
from typing import Optional, List
from datetime import datetime

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
from rich.console import Console

from core.llm import LLM
from core.skills import SkillLoader
from core.tools import ToolRegistry
from core.agent import Agent

console = Console()
logger = logging.getLogger(__name__)

# 全局变量（由 main.py 初始化）
_llm: Optional[LLM] = None
_skill_loader: Optional[SkillLoader] = None
_max_iterations: int = 15


def init(llm: LLM, skill_loader: SkillLoader, max_iterations: int):
    """初始化全局依赖"""
    global _llm, _skill_loader, _max_iterations
    _llm = llm
    _skill_loader = skill_loader
    _max_iterations = max_iterations


# 创建 FastAPI 应用
app = FastAPI(title="Mini Agent", description="遵循 agentskills.io 标准的智能体")

# 确保上传目录存在
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


# ========== 请求/响应模型 ==========
class ChatRequest(BaseModel):
    text: str
    image_paths: Optional[List[str]] = None
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


# ========== 辅助函数：同步转异步 ==========
async def run_agent_async(llm, skill_loader, max_iterations, user_text, image_paths, on_step):
    """在 executor 中运行同步的 agent.run()，避免阻塞事件循环"""
    loop = asyncio.get_event_loop()
    
    def _run():
        tool_registry = ToolRegistry()
        agent = Agent(llm, skill_loader, tool_registry, max_iterations)
        return agent.run(user_text, image_paths, on_step)
    
    return await loop.run_in_executor(None, _run)


# ========== API 端点 ==========
@app.get("/")
async def root():
    """返回 WebUI 页面"""
    html_path = Path(__file__).parent.parent / "webui" / "index.html"
    if html_path.exists():
        # 异步读取文件
        loop = asyncio.get_event_loop()
        content = await loop.run_in_executor(None, html_path.read_text, encoding='utf-8')
        return HTMLResponse(content=content)
    raise HTTPException(status_code=404, detail="WebUI not found")


@app.get("/api/providers")
async def get_providers():
    """获取可用的 Provider 列表"""
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
async def upload_file(file: UploadFile = File(...)):
    """上传文件（图片等）- 异步版本"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename")
    
    # 生成唯一文件名
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = f"{timestamp}_{file.filename}"
    file_path = UPLOAD_DIR / safe_name
    
    # 异步保存文件
    content = await file.read()  # 异步读取上传内容
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, file_path.write_bytes, content)
    
    return {"path": f"/uploads/{safe_name}"}


@app.post("/api/chat")
async def chat(request: ChatRequest):
    """处理对话请求 - 异步版本"""
    global _llm, _skill_loader, _max_iterations
    
    if _llm is None:
        raise HTTPException(status_code=500, detail="LLM not initialized")
    
    steps: List[ToolStep] = []
    
    def on_step(step):
        """回调函数（同步，由 Agent 调用）"""
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
        # thinking 步骤忽略
    
    try:
        # 异步执行 Agent（避免阻塞事件循环）
        answer = await run_agent_async(
            _llm, _skill_loader, _max_iterations,
            request.text, request.image_paths, on_step
        )
        return ChatResponse(reply=answer, steps=steps)
    except Exception as e:
        logger.exception("Chat error")
        raise HTTPException(status_code=500, detail=str(e))


# ========== 静态文件服务 ==========
@app.get("/uploads/{filename}")
async def serve_upload(filename: str):
    """提供上传文件的访问"""
    file_path = UPLOAD_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path)