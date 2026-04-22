import re
import yaml
import logging
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

from core.utils import load_config

logger = logging.getLogger(__name__)

@dataclass
class SkillMeta:
    name: str
    description: str
    path: Path

class SkillLoader:
    def __init__(self, skills_dir: Path | None, enabled: Optional[list[str]] = None):
        """
        skills_dir: skills/ 目录
        enabled: 启用的 skill 名字列表(None 表示全部启用)
        """
        self.skills_dir = skills_dir
        self.enabled = enabled
        self.catalog: dict[str, SkillMeta] = {}

    def scan(self) -> None:
        """
        扫描目录,每个子目录如果有 SKILL.md 就读 frontmatter。
        遵守 agentskills.io 规范验证:
        - name 必填,只能小写字母/数字/连字符,<=64 字符
        - description 必填,<=1024 字符,不含尖括号
        """
        if self.skills_dir is None:
            return

        name_pattern = re.compile(r"^[a-z0-9-]+$")

        for skill_dir in self.skills_dir.iterdir():
            if not skill_dir.is_dir():
                continue

            skill_file = skill_dir / "SKILL.md"
            if not skill_file.exists():
                continue

            content = skill_file.read_text(encoding="utf-8")
            parts = content.split("---", 2)
            if len(parts) < 3:
                continue

            try:
                frontmatter = yaml.safe_load(parts[1].strip()) or {}
            except yaml.YAMLError:
                continue

            name = frontmatter.get("name", "")
            description = frontmatter.get("description", "")

            if not (isinstance(name, str) and name_pattern.match(name) and len(name) <= 64):
                continue

            if not (isinstance(description, str) and len(
                    description) <= 1024 and "<" not in description and ">" not in description):
                continue

            if self.enabled is not None and name not in self.enabled:
                continue

            self.catalog[name] = SkillMeta(
                name=name,
                description=description,
                path=skill_dir
            )

    def get_catalog_text(self) -> str:
        """
        返回给 LLM 的目录说明(轻量元数据)。
        格式示例:
          Available skills (use activate_skill to load details):
          - hello-world: Greet the user...
          - sqlite-sample: Query a sample SQLite database...
        """
        if not self.catalog:
            return "No available skills."

        lines = ["Available skills (use activate_skill to load details):"]

        for meta in sorted(self.catalog.values(), key=lambda x: x.name):
            lines.append(f"- {meta.name}: {meta.description}")
        return "\n".join(lines)

    def load_body(self, name: str) -> str:
        """
        读取指定 skill 的 SKILL.md,去掉 frontmatter 返回正文。
        找不到抛 KeyError。
        """
        if name not in self.catalog:
            raise KeyError(f"Skill not found: {name}")

        skill_file = self.catalog[name].path / "SKILL.md"
        content = skill_file.read_text(encoding="utf-8")
        parts = content.split("---", 2)

        # 返回去掉 frontmatter 的正文，去除首尾空白
        return parts[2].strip() if len(parts) >= 3 else ""

def get_skill_loader() -> SkillLoader:
    config = load_config()
    try:
        skills_dir = Path(config["skills"]["dir"])
    except KeyError:
        logger.error("Skills directory not configured")
        skills_dir = None
    skill_loader = SkillLoader(skills_dir)
    skill_loader.scan()
    return skill_loader