"""
Skill 扫描和加载 - 遵循 agentskills.io 标准
"""
import re
import logging
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, List
import yaml

logger = logging.getLogger(__name__)


@dataclass
class SkillMeta:
    name: str
    description: str
    path: Path
    license: Optional[str] = None
    compatibility: Optional[str] = None
    metadata: Optional[dict] = None


class SkillLoader:
    def __init__(self, skills_dir: Path, enabled: Optional[List[str]] = None):
        self.skills_dir = Path(skills_dir)
        self.enabled = enabled
        self.catalog: dict[str, SkillMeta] = {}
        self._bodies: dict[str, str] = {}

    def scan(self) -> None:
        """扫描 skills/ 目录，加载所有 SKILL.md"""
        if not self.skills_dir.exists():
            logger.warning(f"Skills directory not found: {self.skills_dir}")
            return

        for skill_path in self.skills_dir.iterdir():
            if not skill_path.is_dir():
                continue
            
            md_file = skill_path / "SKILL.md"
            if not md_file.exists():
                continue
            
            content = md_file.read_text(encoding='utf-8')
            
            # 解析 YAML frontmatter
            if not content.startswith('---\n'):
                logger.warning(f"Invalid SKILL.md (no frontmatter): {md_file}")
                continue
            
            parts = content.split('---\n', 2)
            if len(parts) < 3:
                logger.warning(f"Invalid frontmatter in: {md_file}")
                continue
            
            frontmatter_yaml = parts[1]
            body = parts[2].strip()
            
            try:
                frontmatter = yaml.safe_load(frontmatter_yaml)
            except yaml.YAMLError as e:
                logger.warning(f"Failed to parse YAML in {md_file}: {e}")
                continue
            
            name = frontmatter.get('name')
            description = frontmatter.get('description')
            
            # 验证必填字段
            if not name or not description:
                logger.warning(f"Missing name or description in {md_file}")
                continue
            
            # 验证 name 格式
            if not re.match(r'^[a-z0-9-]+$', name) or len(name) > 64:
                logger.warning(f"Invalid skill name '{name}' in {md_file}")
                continue
            
            # 验证 description
            if '<' in description or '>' in description or len(description) > 1024:
                logger.warning(f"Invalid description in {md_file}")
                continue
            
            # 检查是否启用
            if self.enabled is not None and name not in self.enabled:
                logger.info(f"Skill '{name}' disabled by config")
                continue
            
            self.catalog[name] = SkillMeta(
                name=name,
                description=description,
                path=skill_path,
                license=frontmatter.get('license'),
                compatibility=frontmatter.get('compatibility'),
                metadata=frontmatter.get('metadata'),
            )
            self._bodies[name] = body
            logger.info(f"Loaded skill: {name}")

    def get_catalog_text(self) -> str:
        """返回轻量级目录文本"""
        if not self.catalog:
            return "No skills available."
        
        lines = ["Available skills (use activate_skill to load details):"]
        for skill in self.catalog.values():
            lines.append(f"  - {skill.name}: {skill.description}")
        return "\n".join(lines)

    def load_body(self, name: str) -> str:
        """返回 skill 的完整正文"""
        if name not in self._bodies:
            raise KeyError(f"Skill '{name}' not found")
        return self._bodies[name]