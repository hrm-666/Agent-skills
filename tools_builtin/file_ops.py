"""内置文件工具。"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable


MAX_CONTENT_CHARS = 10_000

READ_TOOL = {
    "name": "read",
    "description": "Read the content of a text file. Returns up to 10,000 characters.",
    "parameters": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path (relative or absolute)"}
        },
        "required": ["path"],
    },
}

WRITE_TOOL = {
    "name": "write",
    "description": "Write text content to a file. Creates parent directories if needed. Overwrites existing file.",
    "parameters": {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "content": {"type": "string"},
        },
        "required": ["path", "content"],
    },
}


def create_read_handler(
    root_dir: Path, logger: logging.Logger | None = None
) -> Callable[[str], str]:
    """创建 read 工具 handler。"""
    resolved_root = Path(root_dir).resolve()
    file_logger = logger or logging.getLogger("mini_agent.file_ops")

    def read(path: str) -> str:
        return read_text_file(path=path, root_dir=resolved_root, logger=file_logger)

    return read


def create_write_handler(
    root_dir: Path, logger: logging.Logger | None = None
) -> Callable[[str, str], str]:
    """创建 write 工具 handler。"""
    resolved_root = Path(root_dir).resolve()
    file_logger = logger or logging.getLogger("mini_agent.file_ops")

    def write(path: str, content: str) -> str:
        return write_text_file(
            path=path,
            content=content,
            root_dir=resolved_root,
            logger=file_logger,
        )

    return write


def read_text_file(path: str, root_dir: Path, logger: logging.Logger | None = None) -> str:
    """读取文本文件内容。"""
    file_logger = logger or logging.getLogger("mini_agent.file_ops")

    try:
        target_path = _resolve_target_path(path, root_dir)
    except ValueError as exc:
        return f"[error] {exc}"

    if not target_path.exists():
        return f"[error] File not found: {target_path}"
    if target_path.is_dir():
        return f"[error] Path is a directory, not a file: {target_path}"

    try:
        raw_bytes = target_path.read_bytes()
    except OSError as exc:
        file_logger.exception("读取文件失败: %s", target_path)
        return f"[error] Failed to read file: {exc}"

    if _looks_binary(raw_bytes):
        return f"[error] Binary file is not supported: {target_path}"

    try:
        text = raw_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        return f"[error] Binary file is not supported: {target_path}"

    return _truncate_text(text)


def write_text_file(
    path: str,
    content: str,
    root_dir: Path,
    logger: logging.Logger | None = None,
) -> str:
    """写入文本文件内容。"""
    file_logger = logger or logging.getLogger("mini_agent.file_ops")

    if not isinstance(content, str):
        return "[error] content must be a string"

    try:
        target_path = _resolve_target_path(path, root_dir)
        _ensure_write_allowed(target_path, root_dir)
    except ValueError as exc:
        return f"[error] {exc}"

    if target_path.exists() and target_path.is_dir():
        return f"[error] Path is a directory, not a file: {target_path}"

    try:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(content, encoding="utf-8")
    except OSError as exc:
        file_logger.exception("写入文件失败: %s", target_path)
        return f"[error] Failed to write file: {exc}"

    return f"OK: wrote {len(content)} characters to {target_path}"


def _resolve_target_path(path: str, root_dir: Path) -> Path:
    """将相对或绝对路径解析为绝对路径。"""
    if not isinstance(path, str) or not path.strip():
        raise ValueError("path must be a non-empty string")

    candidate = Path(path.strip())
    if candidate.is_absolute():
        return candidate.resolve()
    return (root_dir / candidate).resolve()


def _ensure_write_allowed(target_path: Path, root_dir: Path) -> None:
    """校验 write 只能落在 workspace/uploads/logs。"""
    allowed_roots = [
        (root_dir / "workspace").resolve(),
        (root_dir / "uploads").resolve(),
        (root_dir / "logs").resolve(),
    ]

    if any(_is_within(target_path, allowed_root) for allowed_root in allowed_roots):
        return

    raise ValueError(
        "write 只能写入 workspace/、uploads/、logs/ 目录，不能写入项目源码"
    )


def _is_within(target_path: Path, parent_path: Path) -> bool:
    """判断 target_path 是否位于 parent_path 内。"""
    try:
        target_path.relative_to(parent_path)
        return True
    except ValueError:
        return False


def _looks_binary(raw_bytes: bytes) -> bool:
    """用轻量规则判断文件是否像二进制。"""
    if b"\x00" in raw_bytes:
        return True
    return False


def _truncate_text(text: str, limit: int = MAX_CONTENT_CHARS) -> str:
    """按约定截断超长文本。"""
    if len(text) <= limit:
        return text
    return (
        text[:limit]
        + f"\n\n[truncated] File content exceeded {limit} characters and was truncated."
    )
