import subprocess, sys, json
from pathlib import Path

SCRIPT = str(Path(__file__).parent.parent / "skills/sqlite-sample/scripts/query.py")
DB = str(Path(__file__).parent.parent / "data/sample.db")


def _run(sql):
    return subprocess.run(
        [sys.executable, SCRIPT, "--sql", sql, "--db", DB],
        capture_output=True, text=True
    )


def test_select_returns_json():
    """合法 SELECT 应返回 JSON 数组"""
    r = _run("SELECT * FROM employees LIMIT 3")
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert isinstance(data, list)
    assert len(data) == 3


def test_non_select_rejected():
    """非 SELECT 语句应以 exit_code=1 退出"""
    r = _run("DROP TABLE employees")
    assert r.returncode == 1


def test_default_limit_100():
    """不带 LIMIT 的查询应默认最多返回 100 条"""
    r = _run("SELECT * FROM employees")
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert len(data) <= 100