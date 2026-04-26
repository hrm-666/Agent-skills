import sqlite3
import json
import argparse
import sys
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# 数据库路径（相对于项目根目录）
DB_PATH = Path(__file__).parent.parent.parent.parent / "data" / "sample.db"


def is_select_sql(sql: str) -> bool:
    """验证 SQL 是否为 SELECT 语句"""
    sql_lower = sql.strip().lower()
    if not sql_lower.startswith("select"):
        return False
    # 禁止危险操作
    dangerous = ["drop", "delete", "insert", "update", "alter", "create"]
    for keyword in dangerous:
        if keyword in sql_lower:
            return False
    return True


def execute_query(sql: str, limit: int = 100) -> dict:
    """执行查询并返回结果"""
    # 自动添加 LIMIT 如果没有
    if "limit" not in sql.lower():
        sql = f"{sql.rstrip(';')} LIMIT {limit}"
    
    logger.info("执行 SQL 查询: %s", sql[:200])
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        cursor.execute(sql)
        rows = cursor.fetchall()
        result = [dict(row) for row in rows]
        logger.info("查询成功，返回 %s 行", len(result))
        return {"success": True, "data": result, "count": len(result)}
    except Exception as e:
        logger.exception("查询执行异常: %s", sql)
        return {"success": False, "error": str(e)}
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="执行 SQLite 查询")
    parser.add_argument("--sql", "-s", required=True, help="SQL 查询语句")
    parser.add_argument("--limit", "-l", type=int, default=100, help="结果数量限制")
    args = parser.parse_args()
    
    # 验证 SQL
    if not is_select_sql(args.sql):
        print(json.dumps({
            "success": False,
            "error": "只允许 SELECT 查询"
        }, ensure_ascii=False))
        sys.exit(1)
    
    # 执行查询
    result = execute_query(args.sql, args.limit)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    
    if not result["success"]:
        sys.exit(1)


if __name__ == "__main__":
    main()