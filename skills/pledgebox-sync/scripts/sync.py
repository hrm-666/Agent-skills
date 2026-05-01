import os
import requests
import hashlib
import json
import pymysql
import time
from datetime import datetime
from pathlib import Path
import traceback
from dotenv import load_dotenv
from init_db import create_database, create_tables

class PledgeBoxSync:
    BASE_URL = "https://api.pledgebox.com/api/openapi/orders"

    def __init__(self):
        self.project_root = Path(__file__).resolve().parents[3]
        self.workspace_dir = self.project_root / "workspace"
        self.uploads_dir = self.project_root / "uploads"
        self.env_file = self.project_root / ".env"
        load_dotenv(dotenv_path=self.env_file)

        self._require_env_vars([
            "PLEDGEBOX_API_TOKEN",
            "PLEDGEBOX_PROJECT_ID",
            "MYSQL_HOST",
            "MYSQL_PORT",
            "MYSQL_USER",
            "MYSQL_DATABASE",
        ])
        self.api_token = os.getenv("PLEDGEBOX_API_TOKEN")
        self.project_id = int(os.getenv("PLEDGEBOX_PROJECT_ID"))

        # 自动初始化数据库
        self._ensure_database_ready()

        self.db = pymysql.connect(
            host=os.getenv("MYSQL_HOST"),
            port=int(os.getenv("MYSQL_PORT", 3306)),
            user=os.getenv("MYSQL_USER"),
            password=os.getenv("MYSQL_PASSWORD"),
            database=os.getenv("MYSQL_DATABASE"),
            cursorclass=pymysql.cursors.DictCursor
        )

    def _require_env_vars(self, keys):
        missing = [k for k in keys if not os.getenv(k)]
        if missing:
            raise ValueError(f"Missing required env vars: {', '.join(missing)} (from {self.env_file})")

    # ---------- ensure database ready ----------
    def _ensure_database_ready(self):
        try:
            print("[INFO] 检查数据库初始化状态...")

            # 创建数据库（如果不存在）
            create_database()

            # 创建表（如果不存在）
            create_tables()

            print("[INFO] 数据库环境已就绪")

        except Exception as e:
            print("[ERROR] 数据库初始化失败:", e)
            raise

    # ---------- hash ----------
    def _hash(self, data):
        return hashlib.md5(json.dumps(data, sort_keys=True).encode()).hexdigest()

    # ---------- API ----------
    def _fetch_orders(self, page):
        for i in range(3):
            try:
                resp = requests.get(self.BASE_URL, params={
                    "api_token": self.api_token,
                    "project_id": self.project_id,
                    "is_completed": 1,
                    "page": page
                })
                resp.raise_for_status()
                time.sleep(0.2)
                return resp.json().get("data", [])
            except Exception:
                if i == 2:
                    raise
                time.sleep(1)

    # ---------- 地址校验 ----------
    def _validate_address(self, cursor, addr):
        if not addr:
            return "invalid"

        zip_code = addr.get("zip")
        country = addr.get("country_code")

        if not country:
            return "invalid"

        if not zip_code:
            return "valid"

        cursor.execute(
            "SELECT 1 FROM geo_reference WHERE country_code=%s AND zip=%s LIMIT 1",
            (country, zip_code)
        )

        return "valid" if cursor.fetchone() else "invalid"

    # ---------- 主流程 ----------
    def run(self):
        started_at = datetime.now()
        inserted = updated = skipped = errors = 0
        deactivated = 0
        page = 1
        current_pbids = set()
        all_orders = []
        inserted_pbids = []
        updated_pbids = []
        skipped_pbids = []
        error_samples = []
        run_error = None
        run_traceback = None

        try:
            with self.db.cursor() as cursor:
                cursor.execute("SELECT GET_LOCK('pledgebox_sync', 10)")
                try:
                    while True:
                        orders = self._fetch_orders(page)
                        if not orders:
                            break

                        all_orders.extend(orders)

                        for order in orders:
                            try:
                                pbid = order["pbid"]
                                current_pbids.add(pbid)

                                data_hash = self._hash(order)
                                cursor.execute(
                                    "SELECT id, data_hash FROM orders WHERE pbid=%s",
                                    (pbid,)
                                )
                                db_order = cursor.fetchone()

                                if not db_order:
                                    self._insert(cursor, order, data_hash)
                                    inserted += 1
                                    if len(inserted_pbids) < 20:
                                        inserted_pbids.append(pbid)
                                elif db_order["data_hash"] != data_hash:
                                    self._update(cursor, db_order["id"], order, data_hash)
                                    updated += 1
                                    if len(updated_pbids) < 20:
                                        updated_pbids.append(pbid)
                                else:
                                    skipped += 1
                                    if len(skipped_pbids) < 20:
                                        skipped_pbids.append(pbid)
                            except Exception as e:
                                errors += 1
                                if len(error_samples) < 20:
                                    error_samples.append(f"{order.get('pbid', 'UNKNOWN')}: {e}")

                        page += 1

                    deactivated = self._deactivate(cursor, current_pbids)
                finally:
                    cursor.execute("SELECT RELEASE_LOCK('pledgebox_sync')")

            self.db.commit()
        except Exception as e:
            self.db.rollback()
            run_error = e
            run_traceback = traceback.format_exc()

        compare_result = self._compare_with_local_orders(all_orders)
        report_path = self._write_markdown_report(
            started_at=started_at,
            ended_at=datetime.now(),
            api_pages=max(page - 1, 0),
            api_order_count=len(all_orders),
            compare_result=compare_result,
            inserted=inserted,
            updated=updated,
            skipped=skipped,
            deactivated=deactivated,
            errors=errors,
            inserted_pbids=inserted_pbids,
            updated_pbids=updated_pbids,
            skipped_pbids=skipped_pbids,
            error_samples=error_samples,
            run_error=run_error,
            run_traceback=run_traceback,
        )

        if run_error is not None:
            raise run_error

        return {
            "inserted": inserted,
            "updated": updated,
            "skipped": skipped,
            "deactivated": deactivated,
            "errors": errors,
            "report_path": str(report_path),
        }

    def _extract_orders_list(self, payload):
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            data = payload.get("data")
            if isinstance(data, list):
                return data
        return []

    def _compare_with_local_orders(self, remote_orders):
        local_file = self.uploads_dir / "orders_full.json"
        result = {
            "file_path": str(local_file),
            "file_exists": local_file.exists(),
            "local_count": 0,
            "remote_count": len(remote_orders),
            "added": 0,
            "removed": 0,
            "changed": 0,
            "unchanged": 0,
            "error": None,
        }
        if not local_file.exists():
            return result

        try:
            payload = json.loads(local_file.read_text(encoding="utf-8"))
            local_orders = self._extract_orders_list(payload)
            result["local_count"] = len(local_orders)

            local_map = {o.get("pbid"): o for o in local_orders if isinstance(o, dict) and o.get("pbid")}
            remote_map = {o.get("pbid"): o for o in remote_orders if isinstance(o, dict) and o.get("pbid")}

            local_pbids = set(local_map.keys())
            remote_pbids = set(remote_map.keys())

            result["added"] = len(remote_pbids - local_pbids)
            result["removed"] = len(local_pbids - remote_pbids)

            changed = 0
            unchanged = 0
            for pbid in (local_pbids & remote_pbids):
                if self._hash(local_map[pbid]) == self._hash(remote_map[pbid]):
                    unchanged += 1
                else:
                    changed += 1

            result["changed"] = changed
            result["unchanged"] = unchanged
            return result
        except Exception as e:
            result["error"] = str(e)
            return result

    def _write_markdown_report(
        self,
        started_at,
        ended_at,
        api_pages,
        api_order_count,
        compare_result,
        inserted,
        updated,
        skipped,
        deactivated,
        errors,
        inserted_pbids,
        updated_pbids,
        skipped_pbids,
        error_samples,
        run_error,
        run_traceback,
    ):
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        filename = f"pledgebox-sync-summary-{started_at.strftime('%Y%m%d-%H%M%S')}.md"
        report_path = self.workspace_dir / filename

        lines = [
            "# PledgeBox Sync Summary",
            "",
            f"- Started At: {started_at.isoformat(sep=' ', timespec='seconds')}",
            f"- Ended At: {ended_at.isoformat(sep=' ', timespec='seconds')}",
            f"- Duration Seconds: {(ended_at - started_at).total_seconds():.2f}",
            f"- Status: {'FAILED' if run_error else 'SUCCESS'}",
            "",
            "## API Fetch",
            "",
            f"- Pages Fetched: {api_pages}",
            f"- Orders Fetched: {api_order_count}",
            "",
            "## Compare With uploads/orders_full.json",
            "",
            f"- File Path: `{compare_result['file_path']}`",
            f"- File Exists: {compare_result['file_exists']}",
        ]

        if compare_result.get("file_exists"):
            lines.extend([
                f"- Local Orders: {compare_result['local_count']}",
                f"- Remote Orders: {compare_result['remote_count']}",
                f"- Added: {compare_result['added']}",
                f"- Removed: {compare_result['removed']}",
                f"- Changed: {compare_result['changed']}",
                f"- Unchanged: {compare_result['unchanged']}",
            ])
            if compare_result.get("error"):
                lines.append(f"- Compare Error: {compare_result['error']}")
        else:
            lines.append("- Compare Result: skipped because local file does not exist")

        lines.extend([
            "",
            "## Database Operations",
            "",
            f"- Inserted: {inserted}",
            f"- Updated: {updated}",
            f"- Skipped (no change): {skipped}",
            f"- Deactivated: {deactivated}",
            f"- Row-level Errors: {errors}",
        ])

        if inserted_pbids:
            lines.extend(["", "### Sample Inserted PBIDs", ""] + [f"- {x}" for x in inserted_pbids])
        if updated_pbids:
            lines.extend(["", "### Sample Updated PBIDs", ""] + [f"- {x}" for x in updated_pbids])
        if skipped_pbids:
            lines.extend(["", "### Sample Skipped PBIDs", ""] + [f"- {x}" for x in skipped_pbids])
        if error_samples:
            lines.extend(["", "### Sample Row Errors", ""] + [f"- {x}" for x in error_samples])

        if run_error is not None:
            lines.extend([
                "",
                "## Run Error",
                "",
                f"- Error: {run_error}",
                "",
                "```text",
                run_traceback or "",
                "```",
            ])

        report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return report_path

    # ---------- 写入 ----------
    def _insert(self, cursor, order, data_hash):

        addr = order.get("shipping_address", {})
        geo_status = self._validate_address(cursor, addr)

        cursor.execute("""
            INSERT INTO orders (pbid, order_status, survey_status, email,
                                paid_amount, credit_offer, balance,
                                courier_name, tracking_code,
                                data_hash, is_active, last_synced_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,1,%s)
        """, (
            order["pbid"],
            order["order_status"],
            order["survey_status"],
            order["email"],
            order["paid_amount"],
            order["credit_offer"],
            order["balance"],
            order.get("courier_name"),
            order.get("tracking_code"),
            data_hash,
            datetime.now()
        ))

        order_id = cursor.lastrowid

        self._insert_address(cursor, order_id, addr, geo_status)
        self._replace_items(cursor, order_id, order)

    def _update(self, cursor, order_id, order, data_hash):

        cursor.execute("""
            UPDATE orders SET data_hash=%s, is_active=1, last_synced_at=%s
            WHERE id=%s
        """, (data_hash, datetime.now(), order_id))

        # 删除子表（顺序重要）
        cursor.execute("""
            DELETE v FROM item_variants v
            JOIN order_items i ON v.item_id = i.id
            WHERE i.order_id=%s
        """, (order_id,))

        cursor.execute("""
            DELETE q FROM item_questions q
            JOIN order_items i ON q.item_id = i.id
            WHERE i.order_id=%s
        """, (order_id,))

        cursor.execute("DELETE FROM order_items WHERE order_id=%s", (order_id,))

        self._replace_items(cursor, order_id, order)

    # ---------- 地址 ----------
    def _insert_address(self, cursor, order_id, addr, geo_status):
        cursor.execute("""
            INSERT INTO order_addresses
            (order_id, recipient_name, phone, address_line1, city,
            state, country, country_code, zip, geo_status)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            order_id,
            addr.get("name"),
            addr.get("phone"),
            addr.get("address"),
            addr.get("city"),
            addr.get("state"),
            addr.get("country"),
            addr.get("country_code"),
            addr.get("zip"),
            geo_status
        ))

    # ---------- 商品 ----------
    def _replace_items(self, cursor, order_id, order):

        def insert(item, source):
            cursor.execute("""
                INSERT INTO order_items (order_id, source_type, product_id, name, sku, price, quantity)
                VALUES (%s,%s,%s,%s,%s,%s,%s)
            """, (
                order_id,
                source,
                item.get("id"),
                item.get("name"),
                item.get("sku"),
                item.get("price", 0),
                item.get("number", 1)
            ))

            item_id = cursor.lastrowid

            # variant
            for v in item.get("variant", []):
                cursor.execute("""
                    INSERT INTO item_variants (item_id, variant_key, variant_value)
                    VALUES (%s,%s,%s)
                """, (
                    item_id,
                    v.get("key") if isinstance(v, dict) else None,
                    v.get("value") if isinstance(v, dict) else str(v)
                ))

            # questions
            for q in item.get("questions", []):
                cursor.execute("""
                    INSERT INTO item_questions (item_id, question, answer)
                    VALUES (%s,%s,%s)
                """, (
                    item_id,
                    q.get("question") if isinstance(q, dict) else str(q),
                    q.get("answer") if isinstance(q, dict) else None
                ))

        if order.get("reward"):
            for i in order["reward"].get("items", []):
                insert(i, "reward")

        for a in order.get("addons", []):
            insert(a, "addon")

        for g in order.get("gifts", []):
            insert(g, "gift")

    # ---------- 失效 ----------
    def _deactivate(self, cursor, pbids):
        if not pbids:
            return 0

        sql = f"""
            UPDATE orders
            SET is_active=0
            WHERE pbid NOT IN ({','.join(['%s']*len(pbids))})
            AND is_active=1
        """

        cursor.execute(sql, tuple(pbids))
        return cursor.rowcount

if __name__ == "__main__":
    sync = PledgeBoxSync()
    print(sync.run())
