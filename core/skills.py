from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml

SKILL_NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


@dataclass
class SkillMeta:
    name: str
    description: str
    path: Path


class SkillLoader:
    def __init__(self, skills_dir: Path, enabled: Optional[list[str]] = None):
        self.skills_dir = skills_dir
        self.enabled = enabled
        self.catalog: dict[str, SkillMeta] = {}
        self.logger = logging.getLogger("mini_agent.skills")

    def scan(self) -> None:
        self.catalog.clear()
        if not self.skills_dir.exists():
            self.logger.warning("Skills directory does not exist: %s", self.skills_dir)
            return

        for child in sorted(self.skills_dir.iterdir()):
            if not child.is_dir():
                continue
            skill_md = child / "SKILL.md"
            if not skill_md.exists():
                continue
            try:
                meta, _ = self._parse_skill_file(skill_md)
                if self.enabled is not None and meta.name not in self.enabled:
                    continue
                self.catalog[meta.name] = meta
            except Exception as exc:
                self.logger.warning("Skip invalid skill file %s: %s", skill_md, exc)

    def get_catalog_text(self) -> str:
        if not self.catalog:
            return "Available skills: (none)"
        lines = ["Available skills (use activate_skill to load details):"]
        for name, meta in sorted(self.catalog.items()):
            lines.append(f"- {name}: {meta.description}")
        return "\n".join(lines)

    def load_body(self, name: str) -> str:
        if name not in self.catalog:
            raise KeyError(name)
        skill_md = self.catalog[name].path / "SKILL.md"
        _, body = self._parse_skill_file(skill_md)
        return body

    def _parse_skill_file(self, path: Path) -> tuple[SkillMeta, str]:
        raw = path.read_text(encoding="utf-8")
        fm_text, body = self._split_frontmatter(raw)
        data = yaml.safe_load(fm_text) if fm_text else {}
        if not isinstance(data, dict):
            raise ValueError("Frontmatter must be a YAML object")

        name = str(data.get("name", "")).strip()
        description = str(data.get("description", "")).strip()
        self._validate_meta(name, description)

        meta = SkillMeta(name=name, description=description, path=path.parent)
        return meta, body.strip()

    def _split_frontmatter(self, raw: str) -> tuple[str, str]:
        if not raw.startswith("---\n"):
            raise ValueError("SKILL.md must start with YAML frontmatter")
        parts = raw.split("---", 2)
        if len(parts) < 3:
            raise ValueError("Invalid frontmatter format")
        return parts[1], parts[2]

    def _validate_meta(self, name: str, description: str) -> None:
        if not name:
            raise ValueError("Skill name is required")
        if len(name) > 64 or not SKILL_NAME_RE.match(name):
            raise ValueError("Invalid skill name format")
        if not description:
            raise ValueError("Skill description is required")
        if len(description) > 1024:
            raise ValueError("Description too long")
        if "<" in description or ">" in description:
            raise ValueError("Description cannot contain angle brackets")
