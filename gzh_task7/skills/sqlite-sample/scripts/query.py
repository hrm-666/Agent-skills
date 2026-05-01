"""
SQLite 示例技能查询脚本
使用方法: python query.py --sql "SELECT ..."
"""

import argparse
import json
import sqlite3
import sys
from pathlib import Path

# 数据库路径（相对于项目根目录）
DB_PATH = Path(__file__).parent.parent.parent.parent / "data" / "sample.db"


def validate_sql(sql: str) -> bool:
    """检查 SQL 是否为 SELECT 语句（安全校验）"""
    sql_lower = sql.strip().lower()
    if not sql_lower.startswith("select"):
        return False
    # 拦截危险模式
    dangerous = [";drop", ";insert", ";update", ";delete", "--", "/*"]
    for pattern in dangerous:
        if pattern in sql_lower:
            return False
    return True


def execute_query(sql: str, limit: int = 100) -> dict:
    """执行 SQL 查询，返回结果字典"""
    
    # 如果没有 LIMIT，自动添加
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