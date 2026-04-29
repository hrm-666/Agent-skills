import argparse
import json
import sys
from import_url import TABLES, get_conn


def rows_to_dicts(cur, rows):
    names = [d[0] for d in cur.description]
    return [dict(zip(names, row)) for row in rows]


def preview(job_id=None, table="api_orders", limit=10):
    if table not in ("api_import_jobs", *TABLES):
        raise RuntimeError(f"Unsupported table: {table}")
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if job_id is None:
                cur.execute("SELECT * FROM api_import_jobs ORDER BY id DESC LIMIT 1")
                row = cur.fetchone()
                if not row:
                    return {"job": None, "counts": {}, "rows": []}
                job = rows_to_dicts(cur, [row])[0]
                job_id = job["id"]
            else:
                cur.execute("SELECT * FROM api_import_jobs WHERE id=%s", (job_id,))
                row = cur.fetchone()
                job = rows_to_dicts(cur, [row])[0] if row else None
            counts = {}
            for name in TABLES:
                cur.execute(f"SELECT COUNT(*) FROM {name} WHERE job_id=%s", (job_id,))
                counts[name] = cur.fetchone()[0]
            if table == "api_import_jobs":
                cur.execute("SELECT * FROM api_import_jobs ORDER BY id DESC LIMIT %s", (limit,))
            else:
                cur.execute(f"SELECT * FROM {table} WHERE job_id=%s ORDER BY id LIMIT %s", (job_id, limit))
            rows = rows_to_dicts(cur, cur.fetchall())
        return {"job": job, "counts": counts, "table": table, "rows": rows}
    finally:
        conn.close()


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Preview MySQL API imports.")
    parser.add_argument("--job-id", type=int)
    parser.add_argument("--table", default="api_orders")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()
    print(json.dumps(preview(args.job_id, args.table, args.limit), ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
