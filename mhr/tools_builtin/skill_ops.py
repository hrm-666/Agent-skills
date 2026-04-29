from __future__ import annotations


def build_activate_skill(skill_loader):
    """返回 activate_skill 工具函数。"""

    def activate_skill(name: str) -> str:
        try:
            return skill_loader.load_body(name)
        except KeyError:
            available = ", ".join(sorted(skill_loader.catalog)) or "none"
            return f"Error: skill '{name}' not found. Available: {available}"

    return activate_skill
