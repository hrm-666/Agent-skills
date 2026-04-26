from __future__ import annotations

import os
from pathlib import Path
import logging
import yaml
from dotenv import load_dotenv

from core.agent import Agent
from core.llm import LLM, PROVIDERS
from core.skills import SkillLoader
from core.tools import ToolRegistry
from tools_builtin.file_ops import read, write
from tools_builtin.shell import bash
from tools_builtin.skill_ops import build_activate_skill
from core.logger import setup_logging

logger = logging.getLogger(__name__)


def create_agent(provider_override: str | None = None) -> Agent:
    # 确保日志已初始化（幂等）
    setup_logging()
    load_dotenv()
    with Path("config.yaml").open("r", encoding="utf-8") as file:
        config = yaml.safe_load(file) or {}

    provider = provider_override or config.get("active_provider", "kimi")
    provider_config = PROVIDERS[provider]
    api_key = os.getenv(provider_config["env_key"])
    if not api_key:
        raise RuntimeError(f"缺少环境变量: {provider_config['env_key']}")

    skill_loader = SkillLoader(Path(config.get("skills", {}).get("dir", "./skills")), config.get("skills", {}).get("enabled"))
    skill_loader.scan()

    tool_registry = ToolRegistry()
    tool_registry.register(
        "read",
        "Read the content of a text file. Returns up to 10,000 characters.",
        {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "File path (relative or absolute)"}},
            "required": ["path"],
        },
        read,
    )
    tool_registry.register(
        "write",
        "Write text content to a file. Creates parent directories if needed. Overwrites existing file.",
        {
            "type": "object",
            "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
            "required": ["path", "content"],
        },
        write,
    )
    tool_registry.register(
        "bash",
        "Execute a shell command. Use this to run skill scripts, curl APIs, install packages, or any command-line operation. Returns stdout+stderr, truncated to 10,000 chars.",
        {
            "type": "object",
            "properties": {
                "command": {"type": "string"},
                "timeout": {"type": "integer", "default": 60, "description": "Seconds"},
            },
            "required": ["command"],
        },
        bash,
    )
    tool_registry.register(
        "activate_skill",
        "Load the full instructions of a specific skill. Use this BEFORE running any skill-related command. The returned text is the skill's complete SKILL.md body.",
        {
            "type": "object",
            "properties": {"name": {"type": "string", "description": "Exact skill name from the catalog"}},
            "required": ["name"],
        },
        build_activate_skill(skill_loader),
    )

    llm = LLM(provider=provider, api_key=api_key, model=config.get("providers", {}).get(provider, {}).get("model"))
    return Agent(
        llm=llm,
        skill_loader=skill_loader,
        tool_registry=tool_registry,
        max_iterations=config.get("agent", {}).get("max_iterations", 15),
    )


def run_cli(message: str) -> str:
    logger.info(f"CLI 请求: {message[:200]}")
    return create_agent().run(message)


def run_interactive() -> None:
    agent = create_agent()
    print("进入交互模式，输入 exit 退出。")
    while True:
        text = input("你> ").strip()
        if text.lower() in {"exit", "quit"}:
            return
        if not text:
            continue
        logger.info(f"CLI 交互消息: {text[:200]}")
        print(agent.run(text))
