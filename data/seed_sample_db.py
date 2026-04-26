from __future__ import annotations

import sqlite3
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


def ensure_sample_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        logger.info("sample.db 已存在: %s", db_path)
        return
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE employees (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                department TEXT NOT NULL,
                salary INTEGER NOT NULL,
                hire_date TEXT NOT NULL
            )
            """
        )
        rows = [
            ("张敏", "Engineering", 32000, "2021-03-15"),
            ("李娜", "Engineering", 29500, "2022-07-10"),
            ("王磊", "Sales", 26000, "2020-09-01"),
            ("赵静", "Sales", 24000, "2023-01-08"),
            ("陈晨", "HR", 21000, "2019-11-12"),
            ("刘洋", "Finance", 28000, "2021-06-18"),
            ("黄杰", "Finance", 30500, "2018-04-22"),
            ("周婷", "Operations", 23000, "2022-02-14"),
            ("吴昊", "Operations", 22500, "2024-05-20"),
            ("孙悦", "Marketing", 25000, "2020-12-03"),
        ]
        conn.executemany(
            "INSERT INTO employees (name, department, salary, hire_date) VALUES (?, ?, ?, ?)",
            rows,
        )
        conn.commit()
    logger.info("已初始化 sample.db: %s, rows_inserted=%s", db_path, len(rows))
