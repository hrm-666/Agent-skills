"""CLI adapter — 极简版。"""

import os
import sys
import logging
from dotenv import load_dotenv

load_dotenv()

from core.agent import Agent
from core.utils import load_config
from core.llm import LLM, PROVIDERS
from core.tools import register_tools
from core.skills import get_skill_loader

logger = logging.getLogger(__name__)

config = load_config()

def build_agent_cli(provider: str | None = None) -> Agent:
    active_provider = provider or config.get("active_provider", "kimi")
    active_provider_cfg = PROVIDERS[active_provider]
    api_key = os.environ.get(active_provider_cfg["env_key"])

    if not api_key:
        logger.error(f"Error: {active_provider_cfg['env_key']} not set")
        sys.exit(1)

    llm = LLM(provider=active_provider, api_key=api_key)
    max_iter = config.get("agent", {}).get("max_iterations", 15)

    return Agent(llm, get_skill_loader(), register_tools(), max_iterations=max_iter)

def run(user_text: str, provider: str | None = None) -> str:
    """执行一次 agent，返回最终文本。"""
    agent = build_agent_cli(provider)
    return agent.run(user_text=user_text)