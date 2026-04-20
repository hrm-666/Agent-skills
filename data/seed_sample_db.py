#!/usr/bin/env python3
"""初始化示例数据库 data/sample.db（含 employees 表及 10 条样本数据）。"""

import sqlite3
from pathlib import Path

_DEFAULT_DB = str(Path(__file__).parent / "sample.db")

_EMPLOYEES = [
    (1,  "张伟", "技术部", 18000, "2021-03-01"),
    (2,  "李娜", "市场部", 12000, "2020-07-15"),
    (3,  "王芳", "人事部", 10000, "2019-11-20"),
    (4,  "刘洋", "技术部", 22000, "2022-01-10"),
    (5,  "陈静", "财务部", 13500, "2021-09-05"),
    (6,  "杨磊", "技术部", 25000, "2018-06-01"),
    (7,  "赵敏", "市场部", 14000, "2023-02-28"),
    (8,  "周杰", "产品部", 17000, "2020-12-01"),
    (9,  "吴雪", "财务部", 11500, "2022-08-17"),
    (10, "郑浩", "产品部", 19000, "2021-05-22"),
]


def seed(db_path: str = _DEFAULT_DB) -> None:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=10)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS employees (
            id         INTEGER PRIMARY KEY,
            name       TEXT NOT NULL,
            department TEXT NOT NULL,
            salary     INTEGER NOT NULL,
            hire_date  TEXT NOT NULL
        )
    """)
    conn.executemany(
        "INSERT OR IGNORE INTO employees VALUES (?,?,?,?,?)",
        _EMPLOYEES
    )
    conn.commit()
    conn.close()
    print(f"[seed] 数据库已就绪: {db_path}")


if __name__ == "__main__":
    seed()
