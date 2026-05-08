#!/usr/bin/env python3
import argparse
import json
import sqlite3
import sys
from pathlib import Path


DB_PATH = Path("data/sample.db")


def normalize_sql(sql: str) -> str:
    cleaned = sql.strip().rstrip(";")
    lowered = cleaned.lower()
    if not lowered.startswith("select"):
        raise ValueError("Only SELECT queries are allowed")
    if " limit " not in lowered:
        cleaned = f"{cleaned} LIMIT 100"
    return cleaned


def run_query(sql: str):
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()
        cursor.execute(sql)
        cols = [d[0] for d in (cursor.description or [])]
        rows = [dict(zip(cols, row)) for row in cursor.fetchall()]
        return rows
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sql", required=True)
    args = parser.parse_args()

    if not DB_PATH.exists():
        print(json.dumps({"error": f"database not found: {DB_PATH}"}, ensure_ascii=False))
        return 1

    try:
        sql = normalize_sql(args.sql)
        rows = run_query(sql)
        print(json.dumps({"count": len(rows), "rows": rows}, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main())
