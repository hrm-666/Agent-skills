from __future__ import annotations

from pathlib import Path
import logging

logger = logging.getLogger(__name__)
MAX_CHARS = 10000
ALLOWED_WRITE_DIRS = ("workspace", "uploads", "logs")


def read(path: str) -> str:
    """读文本文件，最多返回 10000 个字符。"""
   
    file_path = Path(path).expanduser() # expanduser：展开"~""
    if not file_path.is_absolute(): 
        file_path = Path.cwd() / file_path # 如果不是绝对路径就拼接成绝对路径
    logger.info(f"读取文件: {file_path}")

    try:
        text = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        logger.error(f"无法读取二进制文件: {file_path}")
        return f"[error] binary file not supported: {file_path}"
    except FileNotFoundError:
        logger.error(f"文件未找到: {file_path}")
        return f"[error] file not found: {file_path}"

    if len(text) > MAX_CHARS:
        logger.info(f"文件内容过长，已截断: {file_path}")
        return text[:MAX_CHARS] + "\n...[truncated to 10000 chars]"
    return text # 如果超出就截断


def write(path: str, content: str) -> str:
    """只允许写入 workspace、uploads、logs。"""
    file_path = Path(path).expanduser()
    if not file_path.is_absolute():
        file_path = Path.cwd() / file_path
    logger.info(f"写入文件: {file_path}")

    allowed_roots = [(Path.cwd() / name).resolve() for name in ALLOWED_WRITE_DIRS]
    resolved = file_path.resolve()

    if not any(root == resolved or root in resolved.parents for root in allowed_roots):
        logger.error(f"写入路径不允许: {resolved}")
        return f"[error] write path not allowed: {resolved}"

    resolved.parent.mkdir(parents=True, exist_ok=True) # parents=True：自动递归创建多层不存在的父目录,如果父目录不存在就创建，exist_ok=True：如果目录已存在就不报错
    resolved.write_text(content, encoding="utf-8")
    logger.info(f"文件写入成功: {file_path}")
    return f"OK: wrote {len(content)} chars to {resolved}"
