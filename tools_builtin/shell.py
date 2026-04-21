"""内置 shell 工具。"""

from __future__ import annotations

import locale
import logging
import subprocess
from pathlib import Path
from typing import Callable


MAX_OUTPUT_CHARS = 10_000

BASH_TOOL = {
    "name": "bash",
    "description": (
        "Execute a shell command. Use this to run skill scripts, curl APIs, "
        "install packages, or any command-line operation. Returns stdout+stderr, "
        "truncated to 10,000 chars."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "command": {"type": "string"},
            "timeout": {
                "type": "integer",
                "default": 60,
                "description": "Seconds",
            },
        },
        "required": ["command"],
    },
}


def create_bash_handler(
    root_dir: Path, logger: logging.Logger | None = None
) -> Callable[[str, int], str]:
    """创建 bash 工具 handler。"""
    resolved_root = Path(root_dir).resolve()
    shell_logger = logger or logging.getLogger("mini_agent.shell")

    def bash(command: str, timeout: int = 60) -> str:
        return execute_shell_command(
            command=command,
            timeout=timeout,
            root_dir=resolved_root,
            logger=shell_logger,
        )

    return bash


def execute_shell_command(
    command: str,
    timeout: int = 60,
    root_dir: Path | None = None,
    logger: logging.Logger | None = None,
) -> str:
    """执行 shell 命令并返回统一格式的输出。"""
    shell_logger = logger or logging.getLogger("mini_agent.shell")
    working_dir = Path(root_dir or Path.cwd()).resolve()

    if not isinstance(command, str) or not command.strip():
        return "[error] command must be a non-empty string"
    if not isinstance(timeout, int) or timeout <= 0:
        return "[error] timeout must be a positive integer"

    normalized_command = command.strip()
    shell_logger.info(
        "执行 shell 命令: command=%s, timeout=%s, cwd=%s",
        normalized_command,
        timeout,
        working_dir,
    )

    try:
        completed = subprocess.run(
            normalized_command,
            shell=True,
            capture_output=True,
            timeout=timeout,
            cwd=working_dir,
            text=False,
        )
    except subprocess.TimeoutExpired:
        shell_logger.warning("shell 命令超时: command=%s, timeout=%s", normalized_command, timeout)
        return f"[error] Command timed out after {timeout} seconds"
    except Exception as exc:
        shell_logger.exception("shell 命令执行异常: %s", normalized_command)
        return f"[error] Failed to execute command: {exc}"

    shell_logger.info(
        "shell 命令执行完成: exit_code=%s, command=%s",
        completed.returncode,
        normalized_command,
    )

    stdout_text = _decode_output(completed.stdout)
    stderr_text = _decode_output(completed.stderr)
    result = (
        f"[exit_code={completed.returncode}]\n"
        f"STDOUT:\n{stdout_text}\n"
        f"STDERR:\n{stderr_text}"
    )
    return _truncate_output(result)


def _truncate_output(output: str, limit: int = MAX_OUTPUT_CHARS) -> str:
    """按约定截断 shell 输出。"""
    if len(output) <= limit:
        return output
    return (
        output[:limit]
        + f"\n\n[truncated] Shell output exceeded {limit} characters and was truncated."
    )


def _decode_output(raw_output: bytes) -> str:
    """尽量稳妥地解码 shell 输出，兼容 Windows 中文环境。"""
    if not raw_output:
        return ""

    candidates = [
        "utf-8",
        locale.getpreferredencoding(False),
        "gbk",
    ]
    tried: set[str] = set()
    for encoding in candidates:
        if not encoding or encoding in tried:
            continue
        tried.add(encoding)
        try:
            return raw_output.decode(encoding)
        except UnicodeDecodeError:
            continue

    return raw_output.decode("utf-8", errors="replace")
