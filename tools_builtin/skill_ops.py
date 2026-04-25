from __future__ import annotations


def create_activate_skill_handler(skill_loader):
    def activate_skill(name: str) -> str:
        try:
            return skill_loader.load_body(name)
        except KeyError:
            available = ", ".join(sorted(skill_loader.catalog.keys())) or "(none)"
            return f"Error: skill '{name}' not found. Available: {available}"

    return activate_skill
