from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path

import yaml
from dotenv import load_dotenv
from rich.logging import RichHandler

from core.agent import Agent
from core.llm import LLM, PROVIDERS
from core.skills import SkillLoader
from core.tools import ToolRegistry
from tools_builtin.file_ops import create_file_handlers
from tools_builtin.shell import create_bash_handler
from tools_builtin.skill_ops import create_activate_skill_handler

OPENROUTER_MODELS = [
    "moonshotai/kimi-k2.5",
    "qwen/qwen-vl-plus",
    "tencent/hy3-preview:free",
]


def get_project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def load_config(config_path: str | Path = "config.yaml") -> dict:
    root = get_project_root()
    path = Path(config_path)
    if not path.is_absolute():
        path = root / path
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {path}")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def setup_logging(level: str = "INFO") -> None:
    root = get_project_root()
    logs_dir = root / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger()
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.handlers.clear()

    file_path = logs_dir / f"agent-{datetime.now().strftime('%Y-%m-%d')}.log"
    file_handler = logging.FileHandler(file_path, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"))

    rich_handler = RichHandler(rich_tracebacks=True)
    rich_handler.setFormatter(logging.Formatter("%(message)s"))

    logger.addHandler(file_handler)
    logger.addHandler(rich_handler)


def build_agent(config: dict, provider_override: str | None = None, model_override: str | None = None) -> Agent:
    load_dotenv()
    root = get_project_root()

    provider = provider_override or config.get("active_provider", "openrouter")
    if provider not in PROVIDERS:
        raise ValueError(f"Unsupported provider: {provider}")

    provider_cfg = config.get("providers", {}).get(provider, {})
    model = model_override or provider_cfg.get("model") or PROVIDERS[provider]["default_model"]

    env_key = PROVIDERS[provider]["env_key"]
    api_key = os.getenv(env_key, "").strip()
    if not api_key:
        raise ValueError(f"Missing API key in env: {env_key}")

    base_url_env = "OPENROUTER_BASE_URL" if provider == "openrouter" else "DEEPSEEK_BASE_URL"
    base_url = os.getenv(base_url_env) or PROVIDERS[provider]["base_url"]

    llm = LLM(provider=provider, api_key=api_key, model=model, base_url=base_url)

    skills_cfg = config.get("skills", {})
    skills_dir = skills_cfg.get("dir", "./skills")
    skills_path = (root / skills_dir).resolve()
    skill_loader = SkillLoader(skills_path, skills_cfg.get("enabled"))
    skill_loader.scan()

    tool_registry = ToolRegistry()
    read_handler, write_handler = create_file_handlers(root)
    shell_handler = create_bash_handler(root, logging.getLogger("mini_agent.bash"))
    activate_handler = create_activate_skill_handler(skill_loader)

    tool_registry.register(
        name="read",
        description="Read the content of a text file. Returns up to 10,000 characters.",
        parameters={
            "type": "object",
            "properties": {"path": {"type": "string", "description": "File path (relative or absolute)"}},
            "required": ["path"],
        },
        handler=read_handler,
    )
    tool_registry.register(
        name="write",
        description="Write text content to a file. Creates parent directories if needed.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["path", "content"],
        },
        handler=write_handler,
    )
    tool_registry.register(
        name="bash",
        description=(
            "Execute a Windows cmd shell command in the project root and return stdout+stderr. "
            "Prefer Windows-compatible commands such as 'dir', 'type', and 'where' instead of Linux-only flags like 'ls -la'."
        ),
        parameters={
            "type": "object",
            "properties": {
                "command": {"type": "string"},
                "timeout": {"type": "integer", "default": 60},
            },
            "required": ["command"],
        },
        handler=shell_handler,
    )
    tool_registry.register(
        name="activate_skill",
        description="Load the full instructions of a specific skill.",
        parameters={
            "type": "object",
            "properties": {"name": {"type": "string", "description": "Exact skill name from the catalog"}},
            "required": ["name"],
        },
        handler=activate_handler,
    )

    max_iterations = int(config.get("agent", {}).get("max_iterations", 15))
    return Agent(llm=llm, skill_loader=skill_loader, tool_registry=tool_registry, max_iterations=max_iterations)


def get_provider_statuses() -> list[dict]:
    load_dotenv()
    return [
        {
            "name": "openrouter",
            "supports_vision": True,
            "configured": bool(os.getenv("OPENROUTER_API_KEY")),
            "models": OPENROUTER_MODELS,
        },
        {
            "name": "deepseek",
            "supports_vision": False,
            "configured": bool(os.getenv("DEEPSEEK_API_KEY")),
            "models": ["deepseek-chat"],
        },
    ]
