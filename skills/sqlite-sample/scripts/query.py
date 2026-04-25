"""
SQLite query script for sqlite-sample skill.
Usage: python query.py --sql "SELECT ..."
"""

import argparse
import json
import sqlite3
import sys
from pathlib import Path

# Database path relative to project root
DB_PATH = Path(__file__).parent.parent.parent.parent / "data" / "sample.db"


def validate_sql(sql: str) -> bool:
    """Check if SQL is a SELECT statement (security)"""
    sql_lower = sql.strip().lower()
    if not sql_lower.startswith("select"):
        return False
    # Block dangerous patterns
    dangerous = [";drop", ";insert", ";update", ";delete", "--", "/*"]
    for pattern in dangerous:
        if pattern in sql_lower:
            return False
    return True


def execute_query(sql: str, limit: int = 100) -> dict:
    """Execute SQL query and return results as dict"""
    
    # Auto-add LIMIT if not present
    if "limit" not in sql.lower():
        sql = f"{sql.rstrip(';')} LIMIT {limit}"
    
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(sql)
        
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return {
            "success": True,
            "count": len(rows),
            "rows": rows
        }
    except sqlite3.Error as e:
        return {
            "success": False,
            "error": str(e)
        }


def main():
    parser = argparse.ArgumentParser(description="Query SQLite sample database")
    parser.add_argument("--sql", "-s", required=True, help="SELECT SQL statement")
    parser.add_argument("--limit", "-l", type=int, default=100, help="Max rows (default: 100)")
    
    args = parser.parse_args()
    
    if not validate_sql(args.sql):
        print(json.dumps({
            "success": False,
            "error": "Only SELECT statements are allowed"
        }))
        sys.exit(1)
    
    result = execute_query(args.sql, args.limit)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    
    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()