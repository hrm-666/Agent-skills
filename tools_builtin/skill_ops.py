from core.skills import SkillLoader

def activate_skill(name: str, loader: SkillLoader) -> str:
    """加载 Skill 的详细说明"""
    try:
        return loader.load_body(name)
    except KeyError:
        available = list(loader.catalog.keys())
        return f"Error: skill '{name}' not found. Available: {available}"
    except Exception as e:
        return f"Error activating skill: {str(e)}"
