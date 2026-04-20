#!/usr/bin/env python3
"""只允许 SELECT 查询的 SQLite 工具脚本。"""

import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path

_DEFAULT_DB = str(Path(__file__).parent.parent.parent.parent / "data/sample.db")
_DEFAULT_LIMIT = 100


def main() -> None:
    parser = argparse.ArgumentParser(description="SQLite SELECT 查询工具")
    parser.add_argument("--sql", required=True, help='SELECT 语句')
    parser.add_argument("--db", default=_DEFAULT_DB, help="数据库文件路径")
    args = parser.parse_args()

    sql = args.sql.strip()

    # 安全检查：只允许 SELECT
    clean_sql = re.sub(r'--.*', '', sql).strip()
    if not clean_sql.split()[0].lower() == 'select':
        print("错误：只允许 SELECT 语句。", file=sys.stderr)
        sys.exit(1)

    # 自动补 LIMIT
    if not re.search(r'\blimit\b', sql, re.IGNORECASE):
        sql = f"{sql} LIMIT {_DEFAULT_LIMIT}"

    try:
        conn = sqlite3.connect(args.db)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(sql).fetchall()
        conn.close()
    except sqlite3.Error as e:
        print(f"数据库错误: {e}", file=sys.stderr)
        sys.exit(1)

    print(json.dumps([dict(row) for row in rows], ensure_ascii=False))


if __name__ == "__main__":
    main()
