import logging
from pathlib import Path
from typing import Callable

MAX_READ_CHARS = 10_000

logger = logging.getLogger(__name__)


def read_tool() -> tuple[dict, Callable]:
    """
    返回 (schema, handler) 元组。
    read: 读取文本文件内容,最多 MAX_READ_CHARS 字符
    """
    schema = {
        "type": "function",
        "function": {
            "name": "read",
            "description": "Read the content of a text file. Returns up to 10,000 characters.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path (relative or absolute)"
                    }
                },
                "required": ["path"]
            }
        }
    }

    def handler(path: str) -> str:
        """读取文件内容，超长截断，二进制报错"""
        logger.info(f"read tool called with path={path}")
        file_path = Path(path)

        if not file_path.exists():
            return f"Error: File not found: {path}"

        try:
            # 二进制检测
            with open(file_path, "rb"):
                pass
            # 如果走到这里说明不是纯二进制
        except PermissionError:
            return f"Error: Permission denied: {path}"
        except IsADirectoryError:
            return f"Error: Path is a directory, not a file: {path}"
        except Exception as e:
            return f"Error: failed to read file: {e}"

        try:
            # 再尝试文本方式打开
            text = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return f"Error: Binary file cannot be read as text: {path}"

        if len(text) > MAX_READ_CHARS:
            truncated = text[:MAX_READ_CHARS]
            logger.warning(f"read tool: file truncated from {len(text)} to {MAX_READ_CHARS} chars")
            return truncated + f"\n[Truncated: exceeded {MAX_READ_CHARS} char limit]"

        return text

    return schema, handler


# 允许写入的安全目录
SAFE_WRITE_DIRS = {"workspace", "uploads", "logs"}


def write_tool() -> tuple[dict, Callable]:
    """
    write: 写入文本到文件,只能在安全目录内
    """
    schema = {
        "type": "function",
        "function": {
            "name": "write",
            "description": (
                "Write text content to a file. "
                "Creates parent directories if needed. "
                "Overwrites existing file."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string"
                    },
                    "content": {
                        "type": "string"
                    }
                },
        "required": ["path", "content"]
            }
        }
    }

    def handler(path: str, content: str) -> str:
        """写入文件，只允许在 workspace/uploads/logs 目录下"""
        logger.info(f"write tool called with path={path}")
        file_path = Path(path)

        # 安全限制：只允许写入指定目录
        if file_path.anchor:
            # 有锚点（如 /home/xxx），检查是否在安全目录内
            try:
                resolved = file_path.resolve()
            except Exception as e:
                return f"Error: Invalid path: {path}"

            is_safe = any(
                str(resolved).startswith(str(Path.cwd() / safe_dir))
                for safe_dir in SAFE_WRITE_DIRS
            )
            if not is_safe:
                return (
                    f"Error: write is only allowed in directories: "
                    f"{', '.join(SAFE_WRITE_DIRS)}"
                )
        else:
            # 相对路径，检查 cwd 下的子目录
            first_part = str(file_path.parts[0]) if file_path.parts else ""
            if first_part not in SAFE_WRITE_DIRS:
                return (
                    f"Error: write is only allowed in directories: "
                    f"{', '.join(SAFE_WRITE_DIRS)}"
                )

        # 创建父目录
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            return f"Error: Permission denied to create directory: {file_path.parent}"

        # 写入
        try:
            file_path.write_text(content, encoding="utf-8")
            logger.info(f"write tool: successfully wrote {len(content)} chars to {path}")
            return f"Successfully wrote {len(content)} characters to {path}"
        except Exception as e:
            return f"Error writing to {path}: {str(e)}"

    return schema, handler