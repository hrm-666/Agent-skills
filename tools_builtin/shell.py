from __future__ import annotations

import subprocess
from pathlib import Path

MAX_OUTPUT_CHARS = 10000


def create_bash_handler(project_root: Path, logger):
    def bash(command: str, timeout: int = 60) -> str:
        timeout = max(1, min(int(timeout), 600))
        logger.info("bash call: %s", command)
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=str(project_root),
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            logger.error("bash timeout: %s", command)
            return f"[error] command timed out after {timeout}s"
        except Exception as exc:
            logger.error("bash failure: %s", exc)
            return f"[error] command failed: {exc}"

        output = (
            f"[exit_code={result.returncode}]\n"
            f"STDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}"
        )
        if len(output) > MAX_OUTPUT_CHARS:
            output = output[:MAX_OUTPUT_CHARS] + "\n...[truncated]"
        logger.debug("bash result: %s", output)
        return output

    return bash
