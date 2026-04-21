"""CLI adapter — 极简版。"""

import os
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()

from core.agent import Agent
from core import setup_logging
from core.llm import LLM, PROVIDERS
from core.skills import SkillLoader
from core.tools import ToolRegistry
from tools_builtin.file_ops import read_tool, write_tool
from tools_builtin.shell import bash_tool
from tools_builtin.skill_ops import activate_skill_tool


def load_config() -> dict:
  with open("config.yaml", encoding="utf-8") as f:
      return yaml.safe_load(f) or {}


def build_agent(provider: str | None = None) -> Agent:
    config = load_config()
    active_provider = provider or config.get("active_provider", "kimi")
    active_provider_cfg = PROVIDERS[active_provider]

    api_key = os.environ.get(active_provider_cfg["env_key"])
    if not api_key:
      print(f"Error: {active_provider_cfg['env_key']} not set", file=sys.stderr)
      sys.exit(1)

    llm = LLM(provider=active_provider, api_key=api_key)

    skills_dir = Path(config.get("skills", {}).get("dir", "./skills"))
    skill_loader = SkillLoader(skills_dir=skills_dir)
    skill_loader.scan()

    registry = ToolRegistry()
    registry.register(*read_tool())
    registry.register(*write_tool())
    registry.register(*bash_tool())
    registry.register(*activate_skill_tool(skill_loader))

    max_iter = config.get("agent", {}).get("max_iterations", 15)
    return Agent(llm, skill_loader, registry, max_iterations=max_iter)


def run(user_text: str, provider: str | None = None) -> str:
    """执行一次 agent，返回最终文本。"""
    agent = build_agent(provider)
    return agent.run(user_text=user_text)