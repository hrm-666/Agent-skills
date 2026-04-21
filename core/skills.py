import yaml
import logging
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Dict

@dataclass
class SkillMeta:
    name: str
    description: str
    path: Path

class SkillLoader:
    def __init__(self, skills_dir: Path, enabled: Optional[list[str]] = None):
        self.skills_dir = Path(skills_dir)
        self.enabled = enabled
        self.catalog: Dict[str, SkillMeta] = {}

    def scan(self) -> None:
        """扫描目录并加载 SKILL.md 中的元数据"""
        if not self.skills_dir.exists():
            logging.warning(f"Skills directory not found: {self.skills_dir}")
            return

        for skill_path in self.skills_dir.iterdir():
            if not skill_path.is_dir():
                continue
            
            skill_md = skill_path / "SKILL.md"
            if not skill_md.exists():
                continue

            try:
                content = skill_md.read_text(encoding="utf-8")
                # 分离 Frontmatter
                if content.startswith("---"):
                    parts = content.split("---", 2)
                    if len(parts) >= 3:
                        meta_data = yaml.safe_load(parts[1])
                        name = meta_data.get("name")
                        description = meta_data.get("description")
                        
                        if name and description:
                            if self.enabled is None or name in self.enabled:
                                self.catalog[name] = SkillMeta(
                                    name=name,
                                    description=description,
                                    path=skill_path
                                )
                                logging.info(f"Skill loaded: {name}")
                else:
                    logging.warning(f"No frontmatter found in {skill_md}")
            except Exception as e:
                logging.error(f"Failed to load skill at {skill_path}: {e}")

    def get_catalog_text(self) -> str:
        """返回给 LLM 的技能目录说明"""
        if not self.catalog:
            return "No skills available."
        
        lines = ["Available skills (use activate_skill to load details):"]
        for meta in self.catalog.values():
            lines.append(f"- {meta.name}: {meta.description}")
        return "\n".join(lines)

    def load_body(self, name: str) -> str:
        """读取指定 skill 的正文内容"""
        if name not in self.catalog:
            raise KeyError(f"Skill '{name}' not found.")
        
        skill_md = self.catalog[name].path / "SKILL.md"
        content = skill_md.read_text(encoding="utf-8")
        if content.startswith("---"):
            parts = content.split("---", 2)
            return parts[2].strip() if len(parts) >= 3 else ""
        return content.strip()
