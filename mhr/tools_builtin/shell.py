from __future__ import annotations

import locale
import logging
import os
import subprocess

logger = logging.getLogger(__name__)
MAX_CHARS = 10000


def _decode_output(data: bytes) -> str:
    for encoding in ("utf-8", locale.getpreferredencoding(False), "gbk"):
        try:
            return data.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue
    return data.decode("utf-8", errors="replace")


def _should_use_powershell(command: str) -> bool:
    if os.name != "nt":
        return False

    normalized = command.strip().lower()
    unix_like_prefixes = (
        "rm ",
        "ls",
        "pwd",
        "cat ",
        "mv ",
        "cp ",
        "find ",
        "touch ",
        "mkdir ",
    )
    return normalized.startswith(unix_like_prefixes)


def bash(command: str, timeout: int = 60) -> str:
    """执行 shell 命令并返回 stdout + stderr。"""
    logger.info("bash command=%s timeout=%s", command, timeout)

    run_kwargs = {
        "capture_output": True,
        "text": False,
        "timeout": timeout,
    }
    if _should_use_powershell(command):
        logger.info("bash runner=powershell")
        popen_args = ["powershell", "-NoProfile", "-Command", command]
        run_kwargs["shell"] = False
    else:
        logger.info("bash runner=system-shell")
        popen_args = command
        run_kwargs["shell"] = True

    try:
        result = subprocess.run(popen_args, **run_kwargs)
    except subprocess.TimeoutExpired:
        return f"[error] command timed out after {timeout}s"

    stdout = _decode_output(result.stdout or b"")[:MAX_CHARS]
    stderr = _decode_output(result.stderr or b"")[:MAX_CHARS]
    return f"[exit_code={result.returncode}]\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}"
