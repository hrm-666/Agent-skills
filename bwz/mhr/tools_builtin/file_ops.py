from __future__ import annotations

from pathlib import Path

MAX_CHARS = 10000
ALLOWED_WRITE_DIRS = ("workspace", "uploads", "logs")


def read(path: str) -> str:
    """读文本文件，最多返回 10000 个字符。"""
    file_path = Path(path).expanduser()
    if not file_path.is_absolute():
        file_path = Path.cwd() / file_path

    try:
        text = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return f"[error] binary file not supported: {file_path}"
    except FileNotFoundError:
        return f"[error] file not found: {file_path}"

    if len(text) > MAX_CHARS:
        return text[:MAX_CHARS] + "\n...[truncated to 10000 chars]"
    return text


def write(path: str, content: str) -> str:
    """只允许写入 workspace、uploads、logs。"""
    file_path = Path(path).expanduser()
    if not file_path.is_absolute():
        file_path = Path.cwd() / file_path

    allowed_roots = [(Path.cwd() / name).resolve() for name in ALLOWED_WRITE_DIRS]
    resolved = file_path.resolve()

    if not any(root == resolved or root in resolved.parents for root in allowed_roots):
        return f"[error] write path not allowed: {resolved}"

    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(content, encoding="utf-8")
    return f"OK: wrote {len(content)} chars to {resolved}"
