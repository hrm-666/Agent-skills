#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data.seed_sample_db import ensure_sample_db


def normalize_sql(sql: str) -> str:
    """校验并补齐只读查询 SQL。"""
    normalized = sql.strip().rstrip(";")
    lowered = normalized.lower()
    if not lowered.startswith("select"):
        raise ValueError("Only SELECT statements are allowed")
    if ";" in normalized:
        raise ValueError("Only one SELECT statement is allowed")
    if " limit " not in f" {lowered} ":
        normalized = f"{normalized} LIMIT 100"
    return normalized


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sql", required=True)
    args = parser.parse_args()
    sql = normalize_sql(args.sql)

    db_path = PROJECT_ROOT / "data" / "sample.db"
    ensure_sample_db(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(sql).fetchall()
    print(json.dumps([dict(row) for row in rows], ensure_ascii=False))


if __name__ == "__main__":
    main()
