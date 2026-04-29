import sqlite3
from pathlib import Path


EMPLOYEES = [
    ("Alice Zhang", "Engineering", 20000, "2020-01-01"),
    ("Bo Li", "Engineering", 18000, "2022-05-10"),
    ("Cathy Wang", "Engineering", 16000, "2022-12-01"),
    ("David Chen", "Engineering", 15000, "2023-01-15"),
    ("Emma Liu", "Sales", 13000, "2023-06-15"),
    ("Frank Zhao", "Sales", 12000, "2023-03-20"),
    ("Grace Xu", "Product", 11500, "2023-02-10"),
    ("Henry Sun", "Product", 11000, "2022-08-12"),
    ("Iris Huang", "Finance", 9000, "2021-11-05"),
    ("Jack Ma", "HR", 8000, "2023-07-01"),
]


def seed_db(force: bool = False):
    db_path = Path("data/sample.db")
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    if force:
        cursor.execute("DROP TABLE IF EXISTS employees")

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            department TEXT,
            salary REAL,
            hire_date TEXT
        )
        """
    )

    cursor.execute("SELECT COUNT(*) FROM employees")
    row_count = cursor.fetchone()[0]

    if row_count == 0:
        cursor.executemany(
            """
            INSERT INTO employees (name, department, salary, hire_date)
            VALUES (?, ?, ?, ?)
            """,
            EMPLOYEES,
        )
        conn.commit()
        print(f"Sample database seeded with {len(EMPLOYEES)} employees at {db_path}.")
    else:
        print(f"Sample database already has {row_count} employees at {db_path}.")

    conn.close()


if __name__ == "__main__":
    seed_db()
