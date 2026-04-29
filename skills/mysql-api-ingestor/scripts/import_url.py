import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
import re


SENSITIVE_KEYS = {"api_token", "token", "access_token", "key", "api_key", "password", "secret"}
TABLES = ("api_orders", "api_order_addresses", "api_order_line_items", "api_order_attributes")


def load_env() -> None:
    env_path = Path(".env")
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def mask_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    pairs = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    masked = []
    for key, value in pairs:
        if key.lower() in SENSITIVE_KEYS and value:
            shown = value[:4] + "..." + value[-4:] if len(value) > 10 else "***"
            masked.append((key, shown))
        else:
            masked.append((key, value))
    return urllib.parse.urlunsplit(parsed._replace(query=urllib.parse.urlencode(masked)))


def fetch_json(url: str, timeout: int) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": "MiniAgent/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Network error: {exc.reason}") from exc
    try:
        return json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError("Response is not valid JSON.") from exc


def extract_records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict):
        rows = None
        for key in ("data", "orders", "results", "records", "items"):
            if isinstance(payload.get(key), list):
                rows = payload[key]
                break
        if rows is None:
            rows = [payload]
    else:
        raise RuntimeError("JSON payload must be an object or array.")
    return [row for row in rows if isinstance(row, dict)]


def scalar(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return value


def as_decimal(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def jdump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def db_config() -> dict[str, Any]:
    load_env()
    return {
        "host": os.getenv("MYSQL_HOST", "localhost"),
        "port": int(os.getenv("MYSQL_PORT", "3306")),
        "user": os.getenv("MYSQL_USER", "root"),
        "password": os.getenv("MYSQL_PASSWORD", ""),
        "database": os.getenv("MYSQL_DATABASE", "mini_agent_data"),
        "charset": "utf8mb4",
        "autocommit": False,
    }


def get_conn():
    try:
        import pymysql
    except ImportError as exc:
        raise RuntimeError("Missing dependency: pymysql. Install requirements.txt first.") from exc
    cfg = db_config()
    database = cfg.pop("database")
    if not re.fullmatch(r"[A-Za-z0-9_]+", database):
        raise RuntimeError("MYSQL_DATABASE may only contain letters, numbers, and underscores.")
    bootstrap = pymysql.connect(**cfg)
    try:
        with bootstrap.cursor() as cur:
            cur.execute(
                f"CREATE DATABASE IF NOT EXISTS `{database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        bootstrap.commit()
    finally:
        bootstrap.close()
    cfg["database"] = database
    return pymysql.connect(**cfg)


def ensure_tables(cur) -> None:
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS api_import_jobs (
          id BIGINT AUTO_INCREMENT PRIMARY KEY,
          source_url_masked TEXT NOT NULL,
          source_host VARCHAR(255),
          status VARCHAR(32) NOT NULL,
          total_records INT DEFAULT 0,
          success_records INT DEFAULT 0,
          failed_records INT DEFAULT 0,
          error_message TEXT,
          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
          updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS api_orders (
          id BIGINT AUTO_INCREMENT PRIMARY KEY,
          job_id BIGINT NOT NULL,
          source_type VARCHAR(64),
          source_order_id VARCHAR(64),
          pbid VARCHAR(64),
          external_order_id VARCHAR(64),
          email VARCHAR(255),
          order_status VARCHAR(64),
          survey_status VARCHAR(64),
          date_confirmed VARCHAR(64),
          date_completed VARCHAR(64),
          courier_name VARCHAR(128),
          tracking_code VARCHAR(255),
          shipping_amount DECIMAL(14,2),
          tax DECIMAL(14,2),
          value_added_tax DECIMAL(14,2),
          custom_duty DECIMAL(14,2),
          tariff DECIMAL(14,2),
          paid_amount DECIMAL(14,2),
          credit_offer DECIMAL(14,2),
          balance DECIMAL(14,2),
          country_code VARCHAR(16),
          recipient_name VARCHAR(255),
          note TEXT,
          reward_id VARCHAR(64),
          reward_name VARCHAR(255),
          reward_price DECIMAL(14,2),
          raw_json LONGTEXT NOT NULL,
          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
          INDEX idx_job_id (job_id),
          INDEX idx_pbid (pbid),
          INDEX idx_email (email)
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS api_order_addresses (
          id BIGINT AUTO_INCREMENT PRIMARY KEY,
          job_id BIGINT NOT NULL,
          pbid VARCHAR(64),
          name VARCHAR(255),
          phone VARCHAR(128),
          address TEXT,
          address2 TEXT,
          city VARCHAR(128),
          state VARCHAR(128),
          zip VARCHAR(64),
          country VARCHAR(128),
          country_code VARCHAR(16),
          raw_json LONGTEXT,
          INDEX idx_job_pbid (job_id, pbid)
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS api_order_line_items (
          id BIGINT AUTO_INCREMENT PRIMARY KEY,
          job_id BIGINT NOT NULL,
          pbid VARCHAR(64),
          item_group VARCHAR(64) NOT NULL,
          parent_group VARCHAR(64),
          parent_name VARCHAR(255),
          parent_sku VARCHAR(255),
          item_id VARCHAR(64),
          name VARCHAR(255),
          sku VARCHAR(255),
          price DECIMAL(14,2),
          quantity DECIMAL(14,2),
          raw_json LONGTEXT,
          INDEX idx_job_pbid (job_id, pbid),
          INDEX idx_group (item_group)
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS api_order_attributes (
          id BIGINT AUTO_INCREMENT PRIMARY KEY,
          job_id BIGINT NOT NULL,
          pbid VARCHAR(64),
          parent_type VARCHAR(64),
          parent_key VARCHAR(255),
          attr_key VARCHAR(255),
          attr_value TEXT,
          value_type VARCHAR(32),
          raw_json LONGTEXT,
          INDEX idx_job_pbid (job_id, pbid),
          INDEX idx_attr_key (attr_key)
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """
    )


def insert_job(cur, masked_url: str) -> int:
    host = urllib.parse.urlsplit(masked_url).hostname
    cur.execute(
        "INSERT INTO api_import_jobs (source_url_masked, source_host, status) VALUES (%s, %s, %s)",
        (masked_url, host, "running"),
    )
    return int(cur.lastrowid)


def insert_attribute(cur, job_id: int, pbid: str | None, parent_type: str, parent_key: str, key: str, value: Any) -> None:
    cur.execute(
        """
        INSERT INTO api_order_attributes
        (job_id, pbid, parent_type, parent_key, attr_key, attr_value, value_type, raw_json)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        """,
        (job_id, pbid, parent_type, parent_key, key, None if value is None else str(scalar(value)), type(value).__name__, jdump(value)),
    )


def insert_line_item(cur, job_id: int, pbid: str | None, group: str, item: dict[str, Any], parent: dict[str, Any] | None = None) -> None:
    parent = parent or {}
    cur.execute(
        """
        INSERT INTO api_order_line_items
        (job_id, pbid, item_group, parent_group, parent_name, parent_sku, item_id, name, sku, price, quantity, raw_json)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """,
        (
            job_id,
            pbid,
            group,
            parent.get("_group"),
            parent.get("name"),
            parent.get("sku"),
            item.get("id"),
            item.get("name"),
            item.get("sku"),
            as_decimal(item.get("price")),
            as_decimal(item.get("number", item.get("quantity", 1))),
            jdump(item),
        ),
    )
    for key, value in (item.get("variant") or {}).items() if isinstance(item.get("variant"), dict) else []:
        insert_attribute(cur, job_id, pbid, f"{group}_variant", item.get("sku") or item.get("name") or "", key, value)
    for idx, qa in enumerate(item.get("questions") or []):
        if isinstance(qa, dict):
            insert_attribute(cur, job_id, pbid, f"{group}_question", str(item.get("sku") or idx), qa.get("question", f"question_{idx}"), qa.get("answer"))


def insert_order(cur, job_id: int, row: dict[str, Any]) -> None:
    pbid = row.get("pbid") or row.get("pb_id")
    address = row.get("shipping_address") if isinstance(row.get("shipping_address"), dict) else {}
    reward = row.get("reward") if isinstance(row.get("reward"), dict) else {}
    cur.execute(
        """
        INSERT INTO api_orders
        (job_id, source_type, source_order_id, pbid, external_order_id, email, order_status, survey_status,
         date_confirmed, date_completed, courier_name, tracking_code, shipping_amount, tax, value_added_tax,
         custom_duty, tariff, paid_amount, credit_offer, balance, country_code, recipient_name, note,
         reward_id, reward_name, reward_price, raw_json)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """,
        (
            job_id,
            row.get("source"),
            row.get("id"),
            pbid,
            row.get("ks_id") or row.get("sequence"),
            (row.get("email") or "").lower() or None,
            row.get("order_status"),
            row.get("survey_status"),
            row.get("date_confirmed"),
            row.get("date_completed"),
            row.get("courier_name"),
            row.get("tracking_code"),
            as_decimal(row.get("shipping_amount")),
            as_decimal(row.get("tax")),
            as_decimal(row.get("value_added_tax")),
            as_decimal(row.get("custom_duty")),
            as_decimal(row.get("tariff")),
            as_decimal(row.get("paid_amount")),
            as_decimal(row.get("credit_offer")),
            as_decimal(row.get("balance")),
            (address.get("country_code") or row.get("country_code") or "").upper() or None,
            address.get("name") or row.get("name"),
            row.get("note"),
            reward.get("id"),
            reward.get("name"),
            as_decimal(reward.get("price")),
            jdump(row),
        ),
    )
    if address:
        cur.execute(
            """
            INSERT INTO api_order_addresses
            (job_id, pbid, name, phone, address, address2, city, state, zip, country, country_code, raw_json)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                job_id,
                pbid,
                address.get("name"),
                address.get("phone"),
                address.get("address"),
                address.get("address2"),
                address.get("city"),
                address.get("state"),
                address.get("zip"),
                address.get("country"),
                address.get("country_code"),
                jdump(address),
            ),
        )
    for item in reward.get("items") or []:
        if isinstance(item, dict):
            insert_line_item(cur, job_id, pbid, "reward_item", item, {"_group": "reward", "name": reward.get("name")})
    for idx, qa in enumerate(reward.get("questions") or []):
        if isinstance(qa, dict):
            insert_attribute(cur, job_id, pbid, "reward_question", str(reward.get("id") or idx), qa.get("question", f"question_{idx}"), qa.get("answer"))
    for addon in row.get("addons") or []:
        if not isinstance(addon, dict):
            continue
        insert_line_item(cur, job_id, pbid, "addon", addon)
        for child in addon.get("items") or []:
            if isinstance(child, dict):
                insert_line_item(cur, job_id, pbid, "addon_child_item", child, {"_group": "addon", "name": addon.get("name"), "sku": addon.get("sku")})
    for gift in row.get("gifts") or []:
        if isinstance(gift, dict):
            insert_line_item(cur, job_id, pbid, "gift", gift)
    known = {
        "id", "source", "pbid", "pb_id", "ks_id", "sequence", "order_status", "survey_status", "date_confirmed",
        "courier_name", "tracking_code", "email", "shipping_address", "shipping_amount", "tax", "value_added_tax",
        "custom_duty", "tariff", "paid_amount", "credit_offer", "balance", "date_invited", "date_completed",
        "is_dropped", "note", "reward", "addons", "gifts",
    }
    for key, value in row.items():
        if key not in known:
            insert_attribute(cur, job_id, pbid, "order_extra", str(pbid or row.get("id") or ""), key, value)


def import_url(url: str, timeout: int = 30) -> dict[str, Any]:
    payload = fetch_json(url, timeout)
    records = extract_records(payload)
    masked = mask_url(url)
    conn = get_conn()
    job_id = None
    success = failed = 0
    try:
        with conn.cursor() as cur:
            ensure_tables(cur)
            job_id = insert_job(cur, masked)
            for record in records:
                try:
                    insert_order(cur, job_id, record)
                    success += 1
                except Exception:
                    failed += 1
                    insert_attribute(cur, job_id, record.get("pbid") if isinstance(record, dict) else None, "import_error", "", "record", record)
            status = "completed" if failed == 0 else "partial"
            cur.execute(
                "UPDATE api_import_jobs SET status=%s,total_records=%s,success_records=%s,failed_records=%s WHERE id=%s",
                (status, len(records), success, failed, job_id),
            )
        conn.commit()
    except Exception as exc:
        conn.rollback()
        if job_id:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE api_import_jobs SET status=%s,error_message=%s WHERE id=%s",
                    ("failed", str(exc), job_id),
                )
            conn.commit()
        raise
    finally:
        conn.close()
    return {"job_id": job_id, "status": "completed" if failed == 0 else "partial", "total_records": len(records), "success_records": success, "failed_records": failed, "source_url_masked": masked}


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch a JSON API URL and import records into MySQL.")
    parser.add_argument("url")
    parser.add_argument("--timeout", type=int, default=30)
    args = parser.parse_args()
    started = time.time()
    result = import_url(args.url, args.timeout)
    result["elapsed_seconds"] = round(time.time() - started, 2)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(1)
