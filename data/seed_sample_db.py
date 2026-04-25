#!/usr/bin/env python3
import sqlite3
from pathlib import Path


DB_PATH = Path("data/sample.db")

SEED_ROWS = [
    (1, "Alice", "Engineering", 165000, "2019-03-11"),
    (2, "Bob", "Engineering", 148000, "2020-07-21"),
    (3, "Carol", "Finance", 132000, "2018-01-09"),
    (4, "David", "Finance", 128000, "2021-11-02"),
    (5, "Eve", "HR", 99000, "2022-05-13"),
    (6, "Frank", "HR", 103000, "2017-09-30"),
    (7, "Grace", "Sales", 121000, "2020-02-15"),
    (8, "Heidi", "Sales", 126000, "2019-10-18"),
    (9, "Ivan", "Operations", 118000, "2016-06-26"),
    (10, "Judy", "Operations", 123000, "2023-01-08"),
]


def main() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS employees (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                department TEXT NOT NULL,
                salary REAL NOT NULL,
                hire_date TEXT NOT NULL
            )
            """
        )
        cur.execute("DELETE FROM employees")
        cur.executemany(
            "INSERT INTO employees (id, name, department, salary, hire_date) VALUES (?, ?, ?, ?, ?)",
            SEED_ROWS,
        )
        conn.commit()
        print(f"Seeded database at {DB_PATH} with {len(SEED_ROWS)} rows")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
