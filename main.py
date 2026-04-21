import os
import yaml
import logging
import argparse
from pathlib import Path
from dotenv import load_dotenv

from core.llm import LLM
from core.skills import SkillLoader
from core.tools import ToolRegistry
from core.agent import Agent
from adapters.cli import run_cli

# 导入内置工具函数
from tools_builtin.file_ops import read_file, write_file
from tools_builtin.shell import run_bash
from tools_builtin.skill_ops import activate_skill

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - [%(module)s] %(message)s',
        handlers=[
            logging.FileHandler(f"logs/agent.log", encoding='utf-8'),
            logging.StreamHandler()
        ]
    )

def main():
    load_dotenv()
    setup_logging()
    
    # 1. 加载配置
    config_path = Path("config.yaml")
    if not config_path.exists():
        print("Error: config.yaml not found.")
        return
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    # 2. 初始化核心组件
    active_p = config['active_provider']
    provider_cfg = config['providers'][active_p]
    api_key = os.getenv(active_p.upper() + "_API_KEY") # 允许根据提供商动态读取环境变量
    
    # 特殊处理：如果是阿里云提供的桥接 Key
    api_key = api_key or os.getenv("DASHSCOPE_API_KEY") 

    if not api_key:
        print(f"Error: API Key for {active_p} not found in .env")
        return

    llm = LLM(
        provider=active_p,
        api_key=api_key,
        model=provider_cfg.get('model'),
        base_url=provider_cfg.get('base_url')
    )

    skill_loader = SkillLoader(
        skills_dir=Path(config['skills']['dir']),
        enabled=config['skills']['enabled']
    )
    skill_loader.scan()

    tool_registry = ToolRegistry()
    
    # 3. 注册内置工具
    tool_registry.register(
        "read",
        "Read the content of a text file. Returns up to 10,000 characters.",
        {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
        read_file
    )
    tool_registry.register(
        "write",
        "Write text content to a file. Overwrites existing file.",
        {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]},
        write_file
    )
    tool_registry.register(
        "bash",
        "Execute a shell command. Use this to run scripts or command-line operations.",
        {"type": "object", "properties": {"command": {"type": "string"}, "timeout": {"type": "integer"}}, "required": ["command"]},
        run_bash
    )
    # 特殊处理：activate_skill 需要传入 loader 实例
    tool_registry.register(
        "activate_skill",
        "Load the full instructions of a specific skill. Use this BEFORE running any skill-related command.",
        {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
        lambda name: activate_skill(name, skill_loader)
    )

    agent = Agent(
        llm=llm,
        skill_loader=skill_loader,
        tool_registry=tool_registry,
        max_iterations=config['agent']['max_iterations']
    )

    # 4. 命令行参数解析
    parser = argparse.ArgumentParser(description="Mini Agent Runtime")
    subparsers = parser.add_subparsers(dest="command", help="Sub-commands")

    # CLI 模式
    cli_parser = subparsers.add_parser("cli", help="Run in CLI mode")
    cli_parser.add_argument("query", nargs="?", help="Initial query")
    cli_parser.add_argument("--interactive", action="store_true", help="Run in interactive mode")

    # WebUI 模式
    web_parser = subparsers.add_parser("webui", help="Run in WebUI mode")

    # Setup 模式
    setup_parser = subparsers.add_parser("setup", help="Initialize sample data")

    args = parser.parse_args()

    if args.command == "cli":
        run_cli(agent, initial_query=args.query, interactive=args.interactive)
    elif args.command == "webui":
        from adapters.server import start_server
        start_server(agent, config['webui']['host'], config['webui']['port'])
    elif args.command == "setup":
        print("Initializing sample data...")
        from data.seed_sample_db import seed_db
        seed_db()
        print("Setup complete.")
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
