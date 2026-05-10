"""
内置工具：bash（执行 shell 命令，返回结构化结果）
"""
import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)
_MAX_OUTPUT = 10_000
_ROOT_DIR = Path(__file__).resolve().parent.parent


def run_bash(command: str, timeout: int = 60) -> dict:
    """执行 shell 命令，返回结构化 dict。cwd 固定为项目根目录。"""
    logger.info(f"执行 bash 命令：{command[:200]}")
    try:
        proc = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            timeout=timeout,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=_ROOT_DIR,
        )
        stdout, stdout_truncated = _truncate(proc.stdout or "")
        stderr, stderr_truncated = _truncate(proc.stderr or "")
        return {
            "command": command,
            "exit_code": proc.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "timed_out": False,
            "truncated": stdout_truncated or stderr_truncated,
        }
    except subprocess.TimeoutExpired:
        logger.error(f"命令超时（{timeout}s）：{command[:100]}")
        return {
            "command": command,
            "exit_code": None,
            "stdout": "",
            "stderr": f"命令执行超时（{timeout} 秒）",
            "timed_out": True,
            "truncated": False,
        }
    except Exception as e:
        logger.error(f"bash 执行出错：{e}")
        return {
            "command": command,
            "exit_code": None,
            "stdout": "",
            "stderr": f"bash 执行出错：{e}",
            "timed_out": False,
            "truncated": False,
        }


def _truncate(text: str) -> tuple[str, bool]:
    if len(text) <= _MAX_OUTPUT:
        return text, False
    return text[:_MAX_OUTPUT] + f"\n\n[输出已截断，只显示前 {_MAX_OUTPUT} 字符]", True


def register(registry):
    registry.register(
        name="bash",
        description="Execute a shell command. Use this to inspect files, run skill scripts, query databases, or perform command-line operations. Returns structured exit_code/stdout/stderr, truncated to 10,000 chars per stream.",
        parameters={
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to execute"},
                "timeout": {"type": "integer", "default": 60, "description": "Timeout in seconds"},
            },
            "required": ["command"],
        },
        handler=run_bash,
    )
