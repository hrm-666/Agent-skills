import subprocess
import logging

def run_bash(command: str, timeout: int = 60) -> str:
    """执行 Shell 命令"""
    logging.info(f"BASH Call: {command}")
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding='utf-8',
            errors='replace'
        )
        
        output = f"[exit_code={result.returncode}]\n"
        if result.stdout:
            output += f"STDOUT:\n{result.stdout[:5000]}\n"
        if result.stderr:
            output += f"STDERR:\n{result.stderr[:5000]}\n"
            
        if len(output) > 10000:
            output = output[:10000] + "... (truncated)"
        return output
    except subprocess.TimeoutExpired:
        return f"Error: Command timed out after {timeout} seconds."
    except Exception as e:
        return f"Error executing bash: {str(e)}"
