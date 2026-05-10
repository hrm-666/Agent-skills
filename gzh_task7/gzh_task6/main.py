#!/usr/bin/env python3
"""
Mini Agent - 统一入口
"""
import os
import sys
import argparse
import logging
from pathlib import Path
from dotenv import load_dotenv
import yaml

# 加载环境变量
load_dotenv()

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


def load_config():
    """加载配置文件"""
    config_path = Path("config.yaml")
    if not config_path.exists():
        raise FileNotFoundError("config.yaml not found")
    
    with open(config_path) as f:
        return yaml.safe_load(f)


def setup_logging():
    """设置文件日志"""
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    import datetime
    log_file = log_dir / f"agent-{datetime.date.today()}.log"
    
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter('[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s'))
    logging.getLogger().addHandler(file_handler)


def main():
    parser = argparse.ArgumentParser(description="Mini Agent - 遵循 agentskills.io 标准的智能体")
    parser.add_argument("mode", nargs="?", default="cli", choices=["cli", "webui", "setup"],
                        help="运行模式: cli(命令行), webui(网页), setup(初始化)")
    parser.add_argument("message", nargs="?", help="CLI 单次执行的消息")
    parser.add_argument("--interactive", "-i", action="store_true", help="CLI 交互模式")
    
    args = parser.parse_args()
    
    # 加载配置
    try:
        config = load_config()
    except FileNotFoundError:
        print("config.yaml 不存在")
        return
    
    # 设置日志
    setup_logging()
    
    # ========== setup 模式 ==========
    if args.mode == "setup":
        logger.info("Running setup - initializing sample database")
        print("初始化示例数据库...")
        
        # Run seed script
        import subprocess
        result = subprocess.run(
            ["python", "data/seed_sample_db.py"],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print(result.stdout)
            logger.info("Sample database created successfully")
        else:
            print(f"错误: {result.stderr}")
            logger.error(f"Setup failed: {result.stderr}")
        
        return
    
    # ========== webui 模式 ==========
    if args.mode == "webui":
        print("启动 WebUI 模式...")
        
        # 初始化依赖（与 CLI 相同）
        active_provider = config["active_provider"]
        provider_config = config["providers"][active_provider]
        
        env_key_map = {
            "kimi": "MOONSHOT_API_KEY",
            "qwen": "DASHSCOPE_API_KEY",
            "deepseek": "DEEPSEEK_API_KEY",
        }
        
        api_key = os.getenv(env_key_map[active_provider])
        if not api_key:
            print(f"缺少 API Key: {env_key_map[active_provider]} 未在 .env 中设置")
            return
        
        from core.llm import LLM
        llm = LLM(
            provider=active_provider,
            api_key=api_key,
            model=provider_config.get("model")
        )
        
        from core.skills import SkillLoader
        skills_dir = Path(config["skills"]["dir"])
        enabled = config["skills"].get("enabled")
        skill_loader = SkillLoader(skills_dir, enabled)
        skill_loader.scan()
        
        max_iterations = config["agent"]["max_iterations"]
        
        # 初始化 server
        from adapters.server import init as init_server, app
        import uvicorn
        
        init_server(llm, skill_loader, max_iterations)
        
        host = config.get("webui", {}).get("host", "127.0.0.1")
        port = config.get("webui", {}).get("port", 8000)
        
        print(f"WebUI 启动: http://{host}:{port}")
        uvicorn.run(app, host=host, port=port)
        
        return
    
    # ========== CLI 模式 ==========
    # 初始化 LLM
    active_provider = config["active_provider"]
    provider_config = config["providers"][active_provider]
    
    env_key_map = {
        "kimi": "MOONSHOT_API_KEY",
        "qwen": "DASHSCOPE_API_KEY",
        "deepseek": "DEEPSEEK_API_KEY",
    }
    
    api_key = os.getenv(env_key_map[active_provider])
    if not api_key:
        print(f"缺少 API Key: {env_key_map[active_provider]} 未在 .env 中设置")
        return
    
    from core.llm import LLM
    llm = LLM(
        provider=active_provider,
        api_key=api_key,
        model=provider_config.get("model")
    )
    
    # 初始化 SkillLoader
    from core.skills import SkillLoader
    skills_dir = Path(config["skills"]["dir"])
    enabled = config["skills"].get("enabled")
    
    skill_loader = SkillLoader(skills_dir, enabled)
    skill_loader.scan()
    
    max_iterations = config["agent"]["max_iterations"]
    
    from adapters import run_cli, run_once
    
    if args.message:
        run_once(llm, skill_loader, max_iterations, args.message)
    else:
        run_cli(llm, skill_loader, max_iterations)


if __name__ == "__main__":
    main()