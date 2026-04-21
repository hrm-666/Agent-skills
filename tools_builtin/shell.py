from __future__ import annotations

import logging
import subprocess

logger = logging.getLogger(__name__)
MAX_CHARS = 10000


def bash(command: str, timeout: int = 60) -> str:
    """执行 shell 命令并返回 stdout + stderr。"""
    logger.info("bash command=%s timeout=%s", command, timeout)
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return f"[error] command timed out after {timeout}s"

    stdout = result.stdout[:MAX_CHARS]
    stderr = result.stderr[:MAX_CHARS]
    return f"[exit_code={result.returncode}]\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}"
