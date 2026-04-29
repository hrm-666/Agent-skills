from pathlib import Path
from dataclasses import dataclass
from typing import Optional
import yaml
import re

@dataclass
class SkillMeta:
    name: str
    description: str
    path: Path
    # 可选字段: license, compatibility, metadata(dict)

class SkillLoader:
    def __init__(self, skills_dir: Path, enabled: Optional[list[str]] = None):
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
        self.catalog.clear()
        if not self.skills_dir.exists():
            print(f"[Warning] Skills directory '{self.skills_dir}' does not exist.")
            return
        
        for skill_dir in self.skills_dir.iterdir():
            if not skill_dir.is_dir():
                continue

            skill_file = skill_dir / "SKILL.md"
            if not skill_file.exists():
                continue
            
            text = skill_file.read_text(encoding="utf-8")
            meta, _body = self._split_skill_file(text)

            name = meta.get("name")
            description = meta.get("description")

            if not self._is_valid_name(name):
                print(f"[Warning] Skill in '{skill_dir}' has invalid or missing name. Skipping.")
                continue

            if not self._is_valid_description(description):
                print(f"[Warning] Skill '{name}' has invalid or missing description. Skipping.")
                continue

            if self.enabled is not None and name not in self.enabled:
                print(f"[Info] Skill '{name}' is not in enabled list. Skipping.")
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
            return "Available skills: None."
        
        lines = ["Available skills (use activate_skill to load details):"]
        for name in sorted(self.catalog):
            skill = self.catalog[name]
            lines.append(f"- {skill.name}: {skill.description}")
        return "\n".join(lines)
        
    def load_body(self, name: str) -> str:
        """
        读取指定 skill 的 SKILL.md,去掉 frontmatter 返回正文。
        找不到抛 KeyError。
        """
        if name not in self.catalog:
            raise KeyError(f"Skill '{name}' not found in catalog.")
        
        skill_file = self.catalog[name].path / "SKILL.md"
        text = skill_file.read_text(encoding="utf-8")
        _, body = self._split_skill_file(text)
        return body
    def _split_skill_file(self, text: str) -> tuple[dict, str]:
        if not text.startswith("---"):
            return {}, text

        parts = text.split("---", 2)
        if len(parts) < 3:
            return {}, text

        frontmatter = parts[1]
        body = parts[2].lstrip()

        meta = yaml.safe_load(frontmatter) or {}
        return meta, body

    def _is_valid_name(self, name: object) -> bool:
        if not isinstance(name, str):
            return False
        if len(name) > 64:
            return False
        return re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name) is not None

    def _is_valid_description(self, description: object) -> bool:
        if not isinstance(description, str):
            return False
        if not description:
            return False
        if len(description) > 1024:
            return False
        return "<" not in description and ">" not in description
