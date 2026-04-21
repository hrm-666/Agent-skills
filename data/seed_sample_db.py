#!/usr/bin/env python3
"""初始化示例 SQLite 数据库。"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


EMPLOYEES = [
    (1, "张伟", "Engineering", 32000, "2021-03-15"),
    (2, "李娜", "Engineering", 28500, "2022-07-01"),
    (3, "王磊", "Engineering", 35000, "2020-11-20"),
    (4, "陈晨", "Sales", 22000, "2023-01-08"),
    (5, "刘洋", "Sales", 24000, "2021-09-12"),
    (6, "赵敏", "Sales", 26000, "2020-05-03"),
    (7, "孙婷", "Finance", 27000, "2019-12-10"),
    (8, "周强", "Finance", 29500, "2022-04-18"),
    (9, "吴静", "HR", 21000, "2023-06-30"),
    (10, "郑凯", "HR", 23000, "2021-02-25"),
]


def create_sample_db(db_path: Path, force: bool = False) -> str:
    """创建 sample.db。"""
    target = db_path.resolve()
    if target.exists() and not force:
        return f"Skipped: database already exists at {target}. Use --force to recreate it."

    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and force:
        target.unlink()

    conn = sqlite3.connect(target)
    try:
        conn.execute(
            """
            CREATE TABLE employees (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                department TEXT NOT NULL,
                salary INTEGER NOT NULL,
                hire_date TEXT NOT NULL
            )
            """
        )
        conn.executemany(
            """
            INSERT INTO employees (id, name, department, salary, hire_date)
            VALUES (?, ?, ?, ?, ?)
            """,
            EMPLOYEES,
        )
        conn.commit()
    finally:
        conn.close()

    return f"OK: created sample database at {target} with {len(EMPLOYEES)} employees."


def main() -> None:
    parser = argparse.ArgumentParser(description="初始化示例 SQLite 数据库。")
    parser.add_argument(
        "--db-path",
        default=str(Path(__file__).resolve().parent / "sample.db"),
        help="数据库输出路径，默认写入 data/sample.db",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="如果数据库已存在，则删除后重建",
    )
    args = parser.parse_args()

    message = create_sample_db(Path(args.db_path), force=args.force)
    print(message)


if __name__ == "__main__":
    main()
