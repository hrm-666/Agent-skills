"""Skill activation tool."""

import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)


def activate_skill_tool(skill_loader: Any) -> tuple[dict, Callable]:
    """
    activate_skill: 根据 name 加载 skill 完整正文
    skill_loader: SkillLoader 实例
    """
    schema = {
        "type": "function",
        "function": {
            "name": "activate_skill",
            "description": (
                "Load the full instructions of a specific skill. "
                "Use this BEFORE running any skill-related command. "
                "The returned text is the skill's complete SKILL.md body."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Exact skill name from the catalog"
                    }
                },
                "required": ["name"]
            }
        }
    }

    def handler(name: str) -> str:
        """加载指定 skill 的完整内容"""
        logger.info(f"activate_skill tool called: name={name}")

        try:
            body = skill_loader.load_body(name)
            logger.info(f"activate_skill: successfully loaded skill '{name}'")
            return body
        except KeyError:
            available = list(skill_loader.catalog.keys())
            available_str = ", ".join(sorted(available)) if available else "none"
            logger.warning(f"activate_skill: skill '{name}' not found")
            return (
                f"Error: skill '{name}' not found. Available skills: {available_str}"
            )

    return schema, handler