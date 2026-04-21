"""内置 skill 激活工具。"""

from __future__ import annotations

import logging
from typing import Callable

from core.skills import SkillLoader


ACTIVATE_SKILL_TOOL = {
    "name": "activate_skill",
    "description": (
        "Load the full instructions of a specific skill. Use this BEFORE "
        "running any skill-related command. The returned text is the skill's "
        "complete SKILL.md body."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Exact skill name from the catalog",
            }
        },
        "required": ["name"],
    },
}


def create_activate_skill_handler(
    skill_loader: SkillLoader,
    logger: logging.Logger | None = None,
) -> Callable[[str], str]:
    """创建 activate_skill 工具 handler。"""
    skill_logger = logger or logging.getLogger("mini_agent.skill_ops")

    def activate_skill(name: str) -> str:
        return activate_skill_by_name(
            name=name,
            skill_loader=skill_loader,
            logger=skill_logger,
        )

    return activate_skill


def activate_skill_by_name(
    name: str,
    skill_loader: SkillLoader,
    logger: logging.Logger | None = None,
) -> str:
    """按名字加载 skill 正文。"""
    skill_logger = logger or logging.getLogger("mini_agent.skill_ops")

    if not isinstance(name, str) or not name.strip():
        return "[error] name must be a non-empty string"

    normalized_name = name.strip()
    skill_logger.info("激活 skill: %s", normalized_name)

    try:
        return skill_loader.load_body(normalized_name)
    except KeyError:
        available = ", ".join(sorted(skill_loader.catalog)) or "none"
        return f"Error: skill '{normalized_name}' not found. Available: {available}"
    except Exception as exc:
        skill_logger.exception("激活 skill 失败: %s", normalized_name)
        return f"[error] Failed to activate skill '{normalized_name}': {exc}"
