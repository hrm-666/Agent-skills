"""
Skill 操作工具: activate_skill
"""
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.skills import SkillLoader


def make_activate_skill(skill_loader: 'SkillLoader'):
    """工厂函数，创建绑定 skill_loader 的 activate_skill 函数"""
    
    def activate_skill(name: str) -> str:
        """激活 skill，返回完整指令"""
        try:
            body = skill_loader.load_body(name)
            return f"[Skill '{name}' loaded]\n\n{body}"
        except KeyError:
            catalog = skill_loader.get_catalog_text()
            return f"Error: Skill '{name}' not found.\n{catalog}"
    
    return activate_skill