import sqlite3
import os
from pathlib import Path

def seed_db():
    db_path = Path("data/sample.db")
    if db_path.exists():
        print(f"Database already exists at {db_path}")
        return

    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 创建表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS employees (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        department TEXT,
        salary REAL,
        hire_date TEXT
    )
    ''')
    
    # SQLite 不支持 AUTO_INCREMENT 关键字，应该是 AUTOINCREMENT，且必须是 PRIMARY KEY
    # 修正语法
    cursor.execute('DROP TABLE IF EXISTS employees')
    cursor.execute('''
    CREATE TABLE employees (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        department TEXT,
        salary REAL,
        hire_date TEXT
    )
    ''')

    # 插入数据
    employees = [
        ('张三', '研发部', 15000, '2023-01-15'),
        ('李四', '研发部', 18000, '2022-05-10'),
        ('王五', '市场部', 12000, '2023-03-20'),
        ('赵六', '人事部', 9000, '2021-11-05'),
        ('钱七', '财务部', 11000, '2022-08-12'),
        ('孙八', '研发部', 20000, '2020-01-01'),
        ('周九', '市场部', 13000, '2023-06-15'),
        ('吴十', '行政部', 8000, '2023-07-01'),
        ('郑十一', '研发部', 16000, '2022-12-01'),
        ('王十二', '财务部', 11500, '2023-02-10')
    ]

    cursor.executemany(
        'INSERT INTO employees (name, department, salary, hire_date) VALUES (?, ?, ?, ?)',
        employees
    )

    conn.commit()
    conn.close()
    print(f"Sample database created with {len(employees)} records.")

if __name__ == "__main__":
    seed_db()
