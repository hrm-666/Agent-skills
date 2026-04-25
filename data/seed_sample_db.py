#!/usr/bin/env python3
"""
Seed the sample SQLite database with employee data.
Run this script to create data/sample.db.
"""

import sqlite3
from pathlib import Path
from datetime import datetime

DB_PATH = Path(__file__).parent / "sample.db"


def get_sample_employees():
    """Return list of sample employee records"""
    return [
        ("张三", "技术部", 120000, "2020-03-15"),
        ("李四", "技术部", 95000, "2021-06-01"),
        ("王五", "销售部", 110000, "2019-11-20"),
        ("赵六", "市场部", 85000, "2022-01-10"),
        ("陈七", "销售部", 145000, "2018-04-25"),
        ("刘八", "技术部", 78000, "2023-02-14"),
        ("周九", "人事部", 68000, "2021-09-30"),
        ("吴十", "财务部", 92000, "2020-12-01"),
        ("郑十一", "销售部", 135000, "2019-08-12"),
        ("王十二", "技术部", 160000, "2017-05-20"),
    ]


def create_database():
    """Create database and insert sample data"""
    
    # Ensure data directory exists
    DB_PATH.parent.mkdir(exist_ok=True)
    
    # Remove existing database
    if DB_PATH.exists():
        DB_PATH.unlink()
    
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    # Create table
    cursor.execute("""
        CREATE TABLE employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            department TEXT NOT NULL,
            salary INTEGER NOT NULL,
            hire_date TEXT NOT NULL
        )
    """)
    
    # Insert sample data
    employees = get_sample_employees()
    cursor.executemany("""
        INSERT INTO employees (name, department, salary, hire_date)
        VALUES (?, ?, ?, ?)
    """, employees)
    
    conn.commit()
    
    # Verify
    cursor.execute("SELECT COUNT(*) FROM employees")
    count = cursor.fetchone()[0]
    
    conn.close()
    
    print(f"    Database created: {DB_PATH}")
    print(f"   Table: employees ({count} rows)")
    
    # Show sample
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute("SELECT name, salary, department FROM employees ORDER BY salary DESC LIMIT 3")
    print("\n   Top 3 highest paid employees:")
    for row in cursor.fetchall():
        print(f"   - {row[0]}: ${row[1]} ({row[2]})")
    conn.close()


if __name__ == "__main__":
    create_database()