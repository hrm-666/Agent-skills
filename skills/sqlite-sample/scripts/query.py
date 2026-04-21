import sqlite3
import json
import argparse
import sys
from pathlib import Path

def query_db(sql: str):
    db_path = Path("data/sample.db")
    if not db_path.exists():
        return {"error": "Database not found. Please run 'python main.py setup' first."}

    # 安全检查
    if not sql.strip().lower().startswith("select"):
        return {"error": "Only SELECT queries are allowed for security reasons."}

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row  # 返回字典格式
        cursor = conn.cursor()
        
        # 强制增加 LIMIT 100
        if "limit" not in sql.lower():
            sql = sql.rstrip(';') + " LIMIT 100"
            
        cursor.execute(sql)
        rows = cursor.fetchall()
        
        result = [dict(row) for row in rows]
        conn.close()
        return result
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--sql", required=True, help="SQL SELECT query")
    args = parser.parse_args()
    
    res = query_db(args.sql)
    print(json.dumps(res, ensure_ascii=False, indent=2))
