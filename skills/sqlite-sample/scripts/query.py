#!/usr/bin/env python3
"""SQLite 示例查询脚本。"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path


DEFAULT_LIMIT = 100


def get_default_db_path() -> Path:
    """返回默认数据库路径。"""
    return Path(__file__).resolve().parents[3] / "data" / "sample.db"


def normalize_sql(raw_sql: str) -> str:
    """校验并规范化 SQL。"""
    if not isinstance(raw_sql, str) or not raw_sql.strip():
        raise ValueError("Error: --sql is required and must be a non-empty string.")

    sql = raw_sql.strip()
    lowered = sql.lower()
    if not lowered.startswith("select"):
        raise ValueError("Error: only SELECT queries are allowed.")

    # 只允许单条语句；去掉尾部分号后再检查中间是否残留分号。
    sql = sql.rstrip().rstrip(";").strip()
    if ";" in sql:
        raise ValueError("Error: multiple SQL statements are not allowed.")

    if not re.search(r"\blimit\b", sql, flags=re.IGNORECASE):
        sql = f"{sql} LIMIT {DEFAULT_LIMIT}"

    return sql


def run_query(sql: str, db_path: Path) -> dict[str, object]:
    """执行查询并返回结构化结果。"""
    if not db_path.exists():
        raise FileNotFoundError(
            f"Error: database file not found: {db_path}. Run data/seed_sample_db.py first."
        )

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(sql).fetchall()
    finally:
        conn.close()

    result_rows = [dict(row) for row in rows]
    return {
        "sql": sql,
        "row_count": len(result_rows),
        "rows": result_rows,
    }


def build_parser() -> argparse.ArgumentParser:
    """创建命令行参数解析器。"""
    parser = argparse.ArgumentParser(
        description="Run a read-only SELECT query against data/sample.db.",
    )
    parser.add_argument(
        "--sql",
        required=True,
        help='SQL query to run. Example: --sql "SELECT name, salary FROM employees ORDER BY salary DESC"',
    )
    parser.add_argument(
        "--db-path",
        default=str(get_default_db_path()),
        help="Database path. Defaults to data/sample.db.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    try:
        normalized_sql = normalize_sql(args.sql)
        result = run_query(normalized_sql, Path(args.db_path).resolve())
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
