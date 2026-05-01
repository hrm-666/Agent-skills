import argparse
import json
import os
from pathlib import Path

import pymysql
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[3]
ENV_FILE = PROJECT_ROOT / ".env"


def load_project_env():
    load_dotenv(dotenv_path=ENV_FILE)


def require_env_vars(keys):
    missing = [k for k in keys if not os.getenv(k)]
    if missing:
        raise ValueError(f"Missing required env vars: {', '.join(missing)} (from {ENV_FILE})")


def get_connection():
    load_project_env()
    require_env_vars(["MYSQL_HOST", "MYSQL_PORT", "MYSQL_USER", "MYSQL_DATABASE"])
    return pymysql.connect(
        host=os.getenv("MYSQL_HOST"),
        port=int(os.getenv("MYSQL_PORT", 3306)),
        user=os.getenv("MYSQL_USER"),
        password=os.getenv("MYSQL_PASSWORD"),
        database=os.getenv("MYSQL_DATABASE"),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )


def run_query(sql: str):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(sql)
            if cursor.description:
                rows = cursor.fetchall()
                print(json.dumps(rows, ensure_ascii=False, indent=2, default=str))
                print(f"\n[INFO] rows={len(rows)}")
            else:
                print(f"[INFO] affected_rows={cursor.rowcount}")
    finally:
        conn.close()


def show_tables():
    run_query("SHOW TABLES;")


def show_schema(table: str):
    safe_table = table.replace("`", "")
    run_query(f"DESCRIBE `{safe_table}`;")


def main():
    parser = argparse.ArgumentParser(description="Query pledgebox MySQL with .env connection")
    parser.add_argument("--show-tables", action="store_true", help="Show all tables")
    parser.add_argument("--describe", type=str, default="", help="Describe one table")
    parser.add_argument("--sql", type=str, default="", help="Run custom SQL query")
    args = parser.parse_args()

    if args.show_tables:
        show_tables()
        return

    if args.describe:
        show_schema(args.describe)
        return

    if args.sql:
        run_query(args.sql)
        return

    parser.print_help()


if __name__ == "__main__":
    main()
