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
        logger.error(f"命令超时: {command}, timeout={timeout}")
        return f"[error] command timed out after {timeout}s"
    except Exception as e:
        logger.error(f"命令执行异常: {e}")
        return f"[error] command failed: {e}"
    
    # 截断并加提示
    stdout = result.stdout[:MAX_CHARS]
    stderr = result.stderr[:MAX_CHARS]
    
    if len(result.stdout) > MAX_CHARS:
        stdout += "\n... [输出已截断]"
    if len(result.stderr) > MAX_CHARS:
        stderr += "\n... [错误已截断]"
    
    # 构建返回
    output = f"[exit_code={result.returncode}]"
    if stdout:
        output += f"\nSTDOUT:\n{stdout}"
    if stderr:
        output += f"\nSTDERR:\n{stderr}"
    logger.debug(f"命令输出: {output}")
    return output
