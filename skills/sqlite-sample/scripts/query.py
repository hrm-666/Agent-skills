#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sql", required=True)
    args = parser.parse_args()
    sql = args.sql.strip().rstrip(";")
    if not sql.lower().startswith("select"):
        raise ValueError("Only SELECT statements are allowed")
    if " limit " not in sql.lower():
        sql = f"{sql} LIMIT 100"

    db_path = Path("data") / "sample.db"
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(sql).fetchall()
    print(json.dumps([dict(row) for row in rows], ensure_ascii=False))


if __name__ == "__main__":
    main()
