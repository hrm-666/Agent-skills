from __future__ import annotations
import logging

logger = logging.getLogger(__name__)

def build_activate_skill(skill_loader):
    """返回 activate_skill 工具函数。"""

    def activate_skill(name: str) -> str:
        try:
            logger.info(f"激活技能: {name}")
            return skill_loader.load_body(name)
        except KeyError:
            available = ", ".join(sorted(skill_loader.catalog)) or "none"
            logger.error(f"技能未找到: {name}. 可用技能: {available}")
            return f"Error: skill '{name}' not found. Available: {available}"

    return activate_skill
