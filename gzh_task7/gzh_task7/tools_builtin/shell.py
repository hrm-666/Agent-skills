"""
Shell 命令执行工具: bash
"""
import subprocess
import logging

logger = logging.getLogger(__name__)


def run_bash(command: str, timeout: int = 60) -> str:
    """执行 shell 命令"""
    logger.info(f"Bash command: {command[:100]}...")
    
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            timeout=timeout,
            text=True,
        )
        
        output = f"[exit_code={result.returncode}]\n"
        if result.stdout:
            output += f"STDOUT:\n{result.stdout}\n"
        if result.stderr:
            output += f"STDERR:\n{result.stderr}"
        
        if len(output) > 10000:
            output = output[:10000] + "\n... [truncated]"
        
        return output
    except subprocess.TimeoutExpired:
        return f"Error: Command timed out after {timeout}s"
    except Exception as e:
        return f"Error: {e}"