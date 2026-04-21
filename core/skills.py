"""Skill 扫描与加载。"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


SKILL_NAME_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
MAX_NAME_LENGTH = 64
MAX_DESCRIPTION_LENGTH = 1024


@dataclass
class SkillMeta:
    """Skill 目录的轻量元数据。"""

    name: str
    description: str
    path: Path
    license: str | None = None
    compatibility: str | None = None
    metadata: dict[str, Any] | None = None


class SkillLoader:
    """扫描 skills 目录并按需加载 skill。"""

    def __init__(
        self,
        skills_dir: Path,
        enabled: list[str] | None = None,
        logger: logging.Logger | None = None,
    ):
        """
        skills_dir: skills/ 目录
        enabled: 启用的 skill 名字列表（None 表示全部启用）
        """
        self.skills_dir = Path(skills_dir)
        self.enabled = enabled
        self.logger = logger or logging.getLogger("mini_agent.skills")
        self.catalog: dict[str, SkillMeta] = {}

    def scan(self) -> None:
        """扫描 skills 目录，只加载 frontmatter 元数据。"""
        self.catalog = {}

        if not self.skills_dir.exists():
            self.logger.warning("skills 目录不存在: %s", self.skills_dir)
            return
        if not self.skills_dir.is_dir():
            self.logger.warning("skills 路径不是目录: %s", self.skills_dir)
            return

        for child in sorted(self.skills_dir.iterdir(), key=lambda item: item.name):
            if not child.is_dir():
                continue

            skill_file = child / "SKILL.md"
            if not skill_file.is_file():
                continue

            try:
                frontmatter, _ = self._read_skill_markdown(skill_file)
                meta = self._build_skill_meta(child, frontmatter)
            except ValueError as exc:
                self.logger.warning("跳过非法 skill %s: %s", child.name, exc)
                continue

            if self.enabled is not None and meta.name not in self.enabled:
                self.logger.info("skill 未启用，已跳过: %s", meta.name)
                continue

            if meta.name in self.catalog:
                self.logger.warning("发现重复 skill 名称，后者将覆盖前者: %s", meta.name)

            self.catalog[meta.name] = meta

        self.logger.info("扫描完成，共加载 %d 个 skill", len(self.catalog))

    def get_catalog_text(self) -> str:
        """返回给 LLM 的轻量 skill 目录说明。"""
        if not self.catalog:
            return "Available skills (use activate_skill to load details):\n- none"

        lines = ["Available skills (use activate_skill to load details):"]
        for name in sorted(self.catalog):
            meta = self.catalog[name]
            lines.append(f"- {meta.name}: {meta.description}")
        return "\n".join(lines)

    def load_body(self, name: str) -> str:
        """读取指定 skill 的正文，去掉 frontmatter。"""
        if name not in self.catalog:
            raise KeyError(name)

        skill_file = self.catalog[name].path / "SKILL.md"
        _, body = self._read_skill_markdown(skill_file)
        return body

    def _build_skill_meta(self, skill_dir: Path, frontmatter: dict[str, Any]) -> SkillMeta:
        """将 frontmatter 组装并校验成 SkillMeta。"""
        name = self._validate_name(frontmatter.get("name"))
        description = self._validate_description(frontmatter.get("description"))
        if skill_dir.name != name:
            raise ValueError(
                f"目录名 '{skill_dir.name}' 必须与 frontmatter 中的 name '{name}' 一致"
            )

        license_value = frontmatter.get("license")
        compatibility = frontmatter.get("compatibility")
        metadata = frontmatter.get("metadata")

        if license_value is not None and not isinstance(license_value, str):
            raise ValueError("license 必须是字符串")
        if compatibility is not None and not isinstance(compatibility, str):
            raise ValueError("compatibility 必须是字符串")
        if metadata is not None and not isinstance(metadata, dict):
            raise ValueError("metadata 必须是 dict")

        return SkillMeta(
            name=name,
            description=description,
            path=skill_dir,
            license=license_value,
            compatibility=compatibility,
            metadata=metadata,
        )

    def _read_skill_markdown(self, skill_file: Path) -> tuple[dict[str, Any], str]:
        """读取并拆分 SKILL.md 的 frontmatter 与正文。"""
        text = skill_file.read_text(encoding="utf-8")
        if not text.startswith("---"):
            raise ValueError("SKILL.md 必须以 YAML frontmatter 开头")

        parts = text.split("---", 2)
        if len(parts) < 3:
            raise ValueError("SKILL.md 的 YAML frontmatter 没有正确闭合")

        frontmatter_text = parts[1].strip()
        body = parts[2].strip()
        if not frontmatter_text:
            raise ValueError("SKILL.md 的 frontmatter 不能为空")

        try:
            parsed = yaml.safe_load(frontmatter_text)
        except yaml.YAMLError as exc:
            raise ValueError(f"frontmatter YAML 解析失败: {exc}") from exc
        if not isinstance(parsed, dict):
            raise ValueError("SKILL.md 的 frontmatter 顶层必须是 YAML mapping")

        return parsed, body

    def _validate_name(self, name: Any) -> str:
        """严格按 Task6 约束校验 skill 名称。"""
        if not isinstance(name, str) or not name.strip():
            raise ValueError("name 必填且必须是非空字符串")

        normalized = name.strip()
        if len(normalized) > MAX_NAME_LENGTH:
            raise ValueError(f"name 长度不能超过 {MAX_NAME_LENGTH}")
        if not SKILL_NAME_PATTERN.fullmatch(normalized):
            raise ValueError("name 只能包含小写字母、数字、连字符，且不能连续或首尾使用连字符")
        return normalized

    def _validate_description(self, description: Any) -> str:
        """严格按 Task6 约束校验 description。"""
        if not isinstance(description, str) or not description.strip():
            raise ValueError("description 必填且必须是非空字符串")

        normalized = description.strip()
        if len(normalized) > MAX_DESCRIPTION_LENGTH:
            raise ValueError(f"description 长度不能超过 {MAX_DESCRIPTION_LENGTH}")
        if "<" in normalized or ">" in normalized:
            raise ValueError("description 不能包含尖括号")
        return normalized
