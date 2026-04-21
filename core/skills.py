from pathlib import Path
from dataclasses import dataclass
from typing import Optional
import yaml

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

    def get_catalog_text(self) -> str:
        """
        返回给 LLM 的目录说明(轻量元数据)。
        格式示例:
          Available skills (use activate_skill to load details):
          - hello-world: Greet the user...
          - sqlite-sample: Query a sample SQLite database...
        """

    def load_body(self, name: str) -> str:
        """
        读取指定 skill 的 SKILL.md,去掉 frontmatter 返回正文。
        找不到抛 KeyError。
        """