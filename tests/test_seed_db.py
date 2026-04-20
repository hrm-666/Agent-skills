import sqlite3
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_seed_creates_employees_table(tmp_path):
    """seed 函数应创建 employees 表并插入 10 条数据"""
    from data.seed_sample_db import seed
    db_path = str(tmp_path / "test.db")
    seed(db_path)
    conn = sqlite3.connect(db_path)
    count = conn.execute("SELECT COUNT(*) FROM employees").fetchone()[0]
    conn.close()
    assert count == 10

def test_seed_idempotent(tmp_path):
    """多次运行不应重复插入数据"""
    from data.seed_sample_db import seed
    db_path = str(tmp_path / "test.db")
    seed(db_path)
    seed(db_path)
    conn = sqlite3.connect(db_path)
    count = conn.execute("SELECT COUNT(*) FROM employees").fetchone()[0]
    conn.close()
    assert count == 10
