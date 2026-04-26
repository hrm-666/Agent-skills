from pathlib import Path
from dataclasses import dataclass
import re
from typing import Optional
import yaml
import logging

logger = logging.getLogger(__name__)

@dataclass #装饰器，可以快速、简洁地创建 “数据类”
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
        self.catalog: dict[str, SkillMeta] = {} #创建一个空目录，key:str ，value:SkillMeta

    def scan(self) -> None:
        """
        扫描目录,每个子目录如果有 SKILL.md 就读 frontmatter。
        遵守 agentskills.io 规范验证:
        - name 必填,只能小写字母/数字/连字符,<=64 字符
        - description 必填,<=1024 字符,不含尖括号
        """
        logger.info("扫描技能目录: %s", self.skills_dir)
        for subdir in self.skills_dir.iterdir():
            if not subdir.is_dir():
                continue
            skill_md = subdir / "SKILL.md"
            if not skill_md.exists():
                continue
            try:
                content = skill_md.read_text(encoding='utf-8')   #后续需要在这里补充错误检查逻辑
                parts = content.split('---\n', 2)
                frontmatter_raw = parts[1] #取出frontmatter
                frontmatter = yaml.safe_load(frontmatter_raw)
                if not frontmatter:
                    continue
                
                name = frontmatter.get('name')
                description = frontmatter.get('description')
                
                # 验证必填字段
                if not name or not description:
                    continue
                
                # 验证 name 格式
                if len(name) > 64:
                    continue
                if not re.match(r'^[a-z0-9]+(-[a-z0-9]+)*$', name):
                    continue
                
                # 验证 description
                if len(description) > 1024:
                    continue
                if '<' in description or '>' in description:
                    continue
                
                # 检查是否启用
                if self.enabled is not None and name not in self.enabled:
                    continue
                
                # 存入 catalog
                self.catalog[name] = SkillMeta(
                    name=name,
                    description=description,
                    path=subdir
                )
                logger.info("已加载技能: %s from %s", name, skill_md)
                
            except Exception:
                # 解析失败就跳过，不中断
                logger.exception("解析 SKILL.md 失败: %s", skill_md)
                continue

    def get_catalog_text(self) -> str:
        """
        返回给 LLM 的目录说明(轻量元数据)。
        格式示例:
          Available skills (use activate_skill to load details):
          - hello-world: Greet the user...
          - sqlite-sample: Query a sample SQLite database...
        """
        if not self.catalog:
            return "No skills available."
        
        lines = ["Available skills (use activate_skill to load details):"]
        for skill in self.catalog.values():
            lines.append(f"- {skill.name}: {skill.description}")
        logger.debug("返回技能目录文本，count=%s", len(self.catalog))
        
        return "\n".join(lines)

    def load_body(self, name: str) -> str:
        """
        读取指定 skill 的 SKILL.md,去掉 frontmatter 返回正文。
        找不到抛 KeyError。
        """
        if name not in self.catalog:
            logger.error("试图加载不存在的技能: %s", name)
            raise KeyError(f"Skill '{name}' not found")
            
        meta = self.catalog[name]
        skill_md_path = meta.path / "SKILL.md"
        content = skill_md_path.read_text(encoding='utf-8')
        logger.info("读取技能正文: %s", skill_md_path)
        
        # 去掉 frontmatter
        if content.startswith('---\n'):
            parts = content.split('---\n', 2)
            if len(parts) >= 3:
                return parts[2].strip()
        
        return content.strip()
        
