"""
CLI 适配器：单次执行 + 交互式 REPL
"""
import logging
import os
import sys
from pathlib import Path
from typing import Optional

import yaml
from dotenv import load_dotenv
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from core.agent import Agent
from core.llm import LLM, PROVIDERS
from core.skills import SkillLoader
from core.tools import ToolRegistry, ToolPolicy
from tools_builtin.file_ops import register as register_file_ops
from tools_builtin.shell import register as register_shell
from tools_builtin.skill_ops import build_activate_skill
from core.logging_setup import setup_logging

logger = logging.getLogger(__name__)
console = Console()


def create_agent(provider_override: Optional[str] = None) -> Agent:
    setup_logging()
    load_dotenv()
    with Path("config.yaml").open("r", encoding="utf-8") as file:
        config = yaml.safe_load(file) or {}

    provider = provider_override or config.get("active_provider", "kimi")
    provider_config = PROVIDERS[provider]
    api_key = os.getenv(provider_config["env_key"])
    if not api_key:
        raise RuntimeError(f"缺少环境变量: {provider_config['env_key']}")

    skill_loader = SkillLoader(
        Path(config.get("skills", {}).get("dir", "./skills")),
        config.get("skills", {}).get("enabled"),
    )
    skill_loader.scan()

    workspace_dir = config.get("workspace", {}).get("dir", "./workspace")

    tool_policy = ToolPolicy(config.get("tool_policy", {}))
    registry = ToolRegistry(policy=tool_policy)
    register_file_ops(registry, workspace_dir=workspace_dir)
    register_shell(registry)
    registry.register(
        "activate_skill",
        "Load the full instructions of a specific skill. Use this BEFORE running any skill-related command.",
        {
            "type": "object",
            "properties": {"name": {"type": "string", "description": "Exact skill name from the catalog"}},
            "required": ["name"],
        },
        build_activate_skill(skill_loader),
    )

    llm = LLM(
        provider=provider,
        api_key=api_key,
        model=config.get("providers", {}).get(provider, {}).get("model"),
    )
    return Agent(
        llm=llm,
        skill_loader=skill_loader,
        tool_registry=registry,
        max_iterations=config.get("agent", {}).get("max_iterations", 15),
    )


def print_step(step: dict) -> None:
    args_summary = str(step.get("args", ""))[:80]
    console.print(f"  [yellow]🔧 {step['name']}({args_summary})[/yellow]")


def run_cli(message: str) -> str:
    logger.info(f"CLI 请求: {message[:200]}")
    agent = create_agent()
    reply, steps = agent.run(message, on_step=print_step)
    console.print()
    console.print(Panel(Markdown(reply), title="[bold green]Agent 回复[/bold green]", border_style="green"))
    return reply


def run_interactive() -> None:
    agent = create_agent()
    console.print(Panel(
        "[bold]czon Agent — 交互模式[/bold]\n输入消息后按 Enter 发送，输入 [cyan]exit[/cyan] 或 [cyan]quit[/cyan] 退出",
        border_style="blue",
    ))
    while True:
        try:
            text = console.input("[bold cyan]>>> [/bold cyan]").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]已退出[/dim]")
            break
        if not text:
            continue
        if text.lower() in ("exit", "quit", "q"):
            console.print("[dim]再见！[/dim]")
            break
        try:
            reply, _ = agent.run(text, on_step=print_step)
            console.print()
            console.print(Panel(Markdown(reply), title="[bold green]Agent[/bold green]", border_style="green"))
            console.print()
        except Exception as e:
            logger.error(f"执行出错：{e}", exc_info=True)
            console.print(f"[bold red]错误：{e}[/bold red]\n")
