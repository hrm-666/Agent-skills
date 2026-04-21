import os
import shutil
import logging
from typing import List, Optional
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from pathlib import Path
from core.agent import Agent
from core.llm import PROVIDERS

class ChatRequest(BaseModel):
    text: str
    image_paths: Optional[List[str]] = []
    provider: str

app = FastAPI()
_agent: Optional[Agent] = None

def start_server(agent_instance: Agent, host: str, port: int):
    global _agent
    _agent = agent_instance
    
    # 挂载静态文件和上传目录
    app.mount("/webui", StaticFiles(directory="webui"), name="webui")
    app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
    
    import uvicorn
    logging.info(f"Starting WebUI server at http://{host}:{port}/webui/index.html")
    uvicorn.run(app, host=host, port=port)

@app.post("/api/chat")
async def chat(request: ChatRequest):
    if not _agent:
        raise HTTPException(status_code=500, detail="Agent not initialized")
    
    # 更新 LLM provider (简单起见，这里假设 Agent 初始化时已经加载了所有 provider)
    # 实际上可能需要一个 factory 或在 agent.run 中处理重启
    # MVP 暂时只支持初始化时的默认 provider，如果需要动态切换，可以临时修改 _agent.llm
    
    steps = []
    def on_step(step_data):
        steps.append(step_data)

    try:
        reply = _agent.run(
            user_text=request.text,
            image_paths=request.image_paths,
            on_step=on_step
        )
        return {"reply": reply, "steps": steps}
    except Exception as e:
        logging.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    uploads_dir = Path("uploads")
    uploads_dir.mkdir(exist_ok=True)
    
    file_path = uploads_dir / file.filename
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    return {"path": f"/uploads/{file.filename}"}

@app.get("/api/providers")
async def get_providers():
    result = []
    for name, cfg in PROVIDERS.items():
        env_key = cfg['env_key']
        # 注意：用户提供的阿里云 key 可能填在不同的 env_key 下
        # 我们的 main.py 有后备逻辑，这里简单判断环境变量
        configured = bool(os.getenv(env_key) or os.getenv("DASHSCOPE_API_KEY"))
        result.append({
            "name": name,
            "supports_vision": cfg['supports_vision'],
            "configured": configured
        })
    return result
