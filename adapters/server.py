"""
FastAPI 服务器 - WebUI 后端
"""
import os
import logging
import shutil
from pathlib import Path
from typing import Optional, List
from datetime import datetime

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
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


# ========== API 端点 ==========
@app.get("/")
async def root():
    """返回 WebUI 页面"""
    html_path = Path(__file__).parent.parent / "webui" / "index.html"
    if html_path.exists():
        return HTMLResponse(content=html_path.read_text(encoding='utf-8'))
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
    """上传文件（图片等）"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename")
    
    # 生成唯一文件名
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = f"{timestamp}_{file.filename}"
    file_path = UPLOAD_DIR / safe_name
    
    # 保存文件
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    
    # 返回可访问的路径
    return {"path": f"/uploads/{safe_name}"}


@app.post("/api/chat")
async def chat(request: ChatRequest):
    """处理对话请求"""
    global _llm, _skill_loader, _max_iterations
    
    if _llm is None:
        raise HTTPException(status_code=500, detail="LLM not initialized")
    
    tool_registry = ToolRegistry()
    agent = Agent(_llm, _skill_loader, tool_registry, _max_iterations)
    
    steps: List[ToolStep] = []
    
    def on_step(step):
        if step["type"] == "tool_call":
            steps.append(ToolStep(
                type="tool_call",
                name=step["name"],
                args=step["args"]
            ))
        elif step["type"] == "tool_result":
            # 找到最后一个 tool_call 并添加结果
            for s in reversed(steps):
                if s.type == "tool_call" and s.result is None:
                    s.result = step["result"][:500]
                    break
        elif step["type"] == "thinking":
            pass  # 忽略思考步骤
    
    try:
        answer = agent.run(
            user_text=request.text,
            image_paths=request.image_paths,
            on_step=on_step
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