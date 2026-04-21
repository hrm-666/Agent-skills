import logging
import subprocess
from typing import Any, Callable

DEFAULT_TIMEOUT = 60
MAX_OUTPUT_CHARS = 10000

logger = logging.getLogger(__name__)


def bash_tool() -> tuple[dict, Callable]:
  """
  bash: 执行 shell 命令，返回格式化的 stdout+stderr
  """
  schema = {
      "type": "function",
      "function": {
          "name": "bash",
          "description": (
              "Execute a shell command. Use this to run skill scripts, curl APIs, "
              "install packages, or any command-line operation. "
              "Returns stdout+stderr, truncated to 10,000 chars."
          ),
          "parameters": {
              "type": "object",
              "properties": {
                  "command": {
                      "type": "string"
                  },
                  "timeout": {
                      "type": "integer",
                      "default": DEFAULT_TIMEOUT,
                      "description": "Seconds"
                  }
              },
              "required": ["command"]
          }
      }
  }

  def handler(command: str, timeout: int = DEFAULT_TIMEOUT) -> str:
      """执行 shell 命令并返回格式化输出"""
      logger.info(f"bash tool called: command={command[:200]}")

      try:
          result = subprocess.run(
              command,
              shell=True,
              capture_output=True,
              timeout=timeout,
              text=True,
              encoding="utf-8",
              errors="replace"
          )
      except subprocess.TimeoutExpired:
          logger.error(f"bash tool: command timed out after {timeout}s")
          return f"Error: Command timed out after {timeout} seconds"
      except Exception as e:
          logger.error(f"bash tool: execution error: {e}")
          return f"Error executing command: {str(e)}"

      # 格式化输出
      stdout = result.stdout if result.stdout else ""
      stderr = result.stderr if result.stderr else ""

      output_lines = [
          f"[exit_code={result.returncode}]",
          "STDOUT:",
          stdout,
          "STDERR:",
          stderr
      ]
      full_output = "\n".join(output_lines)

      # 截断超长输出
      if len(full_output) > MAX_OUTPUT_CHARS:
          truncated = full_output[:MAX_OUTPUT_CHARS]
          logger.warning(
              f"bash tool: output truncated from {len(full_output)} "
              f"to {MAX_OUTPUT_CHARS} chars"
          )
          return (
              truncated
              + f"\n[Output truncated: exceeded {MAX_OUTPUT_CHARS} char limit]"
          )

      logger.info(f"bash tool: completed with exit_code={result.returncode}")
      return full_output

  return schema, handler