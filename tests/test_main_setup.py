import subprocess, sys
from pathlib import Path

ROOT = str(Path(__file__).parent.parent)

def test_setup_exits_zero():
    """python main.py setup 应成功退出"""
    result = subprocess.run(
        [sys.executable, "main.py", "setup"],
        capture_output=True, text=True, cwd=ROOT
    )
    assert result.returncode == 0
    assert "就绪" in result.stdout
