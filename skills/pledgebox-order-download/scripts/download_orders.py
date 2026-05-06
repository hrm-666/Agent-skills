from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


BASE_URL = "https://api.pledgebox.com/api/openapi/orders"

ORDER_FIELDS = [
    "order_id",
    "pbid",
    "ks_id",
    "sequence",
    "project_id",
    "order_status",
    "survey_status",
    "date_confirmed",
    "courier_name",
    "tracking_code",
    "email",
    "paid_amount",
    "credit_offer",
    "balance",
    "recipient_name",
    "country",
    "country_code",
    "state",
    "city",
    "zip",
    "address",
    "address2",
    "phone",
    "raw_json",
]

ITEM_FIELDS = [
    "order_id",
    "pbid",
    "item_source",
    "reward_id",
    "reward_name",
    "reward_price",
    "product_id",
    "product_name",
    "sku",
    "variant",
    "quantity",
    "price",
    "raw_json",
]

QUESTION_FIELDS = [
    "order_id",
    "pbid",
    "question_scope",
    "item_source",
    "product_id",
    "question",
    "answer",
    "raw_json",
]

SUMMARY_FIELDS = [
    "project_id",
    "base_url",
    "is_completed",
    "order_status",
    "pages_requested",
    "orders_count",
    "items_count",
    "questions_count",
    "errors_count",
    "started_at",
    "finished_at",
    "output_dir",
    "raw_json_file",
    "orders_file",
    "order_items_file",
    "questions_file",
    "errors_file",
]

ERROR_FIELDS = [
    "level",
    "stage",
    "page",
    "order_id",
    "pbid",
    "message",
    "raw_json",
]


def compact_token(token: str | None) -> str:
    if token is None:
        return ""
    return "".join(str(token).split())


def json_cell(value: Any) -> str:
    if value is None:
        return ""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def safe_get(data: Any, key: str, default: Any = "") -> Any:
    if isinstance(data, dict):
        value = data.get(key, default)
        return default if value is None else value
    return default


def nested_get(data: Any, path: str, default: Any = "") -> Any:
    current = data
    for part in path.split("."):
        if not isinstance(current, dict):
            return default
        current = current.get(part)
        if current is None:
            return default
    return current


def ensure_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value in (None, ""):
        return []
    return [value]


def parse_orders_from_payload(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        candidates = payload
    elif isinstance(payload, dict):
        data = payload.get("data", payload.get("orders", []))
        if isinstance(data, dict):
            candidates = data.get("data", data.get("orders", []))
        else:
            candidates = data
    else:
        raise ValueError("API response is neither a list nor an object")

    if candidates in (None, ""):
        return []
    if not isinstance(candidates, list):
        raise ValueError("API response data is not a list")

    orders: list[dict[str, Any]] = []
    for item in candidates:
        if isinstance(item, dict):
            orders.append(item)
        else:
            raise ValueError("API response contains a non-object order")
    return orders


def request_page(
    api_token: str,
    project_id: int,
    page: int,
    is_completed: int | None,
    order_status: str,
    pb_id: str,
    email: str,
) -> Any:
    params: dict[str, Any] = {
        "api_token": api_token,
        "project_id": project_id,
        "page": page,
    }
    if is_completed is not None:
        params["is_completed"] = is_completed
    if order_status:
        params["order_status"] = order_status
    if pb_id:
        params["pb_id"] = pb_id
    if email:
        params["email"] = email

    url = f"{BASE_URL}?{urlencode(params)}"
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "pledgebox-order-download/1.0"})

    with urlopen(request, timeout=30) as response:
        body = response.read().decode("utf-8-sig")
    return json.loads(body)


def fetch_orders(
    api_token: str,
    project_id: int,
    is_completed: int | None,
    order_status: str,
    max_pages: int,
    pb_id: str,
    email: str,
) -> tuple[list[dict[str, Any]], int, list[dict[str, Any]]]:
    all_orders: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    pages_requested = 0

    for page in range(1, max_pages + 1):
        pages_requested = page
        try:
            payload = request_page(api_token, project_id, page, is_completed, order_status, pb_id, email)
            page_orders = parse_orders_from_payload(payload)
        except HTTPError as exc:
            body = ""
            try:
                body = exc.read().decode("utf-8", errors="replace")
            except Exception:
                body = str(exc)
            errors.append(error_row("error", "api_request", page, None, None, f"HTTP {exc.code}: {body[:500]}", None))
            break
        except (URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
            errors.append(error_row("error", "api_request", page, None, None, str(exc), None))
            break

        if not page_orders:
            break

        all_orders.extend(page_orders)
        print(f"downloaded page={page}, page_orders={len(page_orders)}, total_orders={len(all_orders)}")
        time.sleep(0.3)

        if pb_id or email:
            break

    return all_orders, pages_requested, errors


def error_row(
    level: str,
    stage: str,
    page: int | None,
    order_id: Any,
    pbid: Any,
    message: str,
    raw_json: Any,
) -> dict[str, Any]:
    return {
        "level": level,
        "stage": stage,
        "page": "" if page is None else page,
        "order_id": "" if order_id is None else order_id,
        "pbid": "" if pbid is None else pbid,
        "message": message,
        "raw_json": json_cell(raw_json),
    }


def flatten_orders(orders: list[dict[str, Any]], project_id: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for order in orders:
        rows.append(
            {
                "order_id": safe_get(order, "id"),
                "pbid": safe_get(order, "pbid"),
                "ks_id": safe_get(order, "ks_id"),
                "sequence": safe_get(order, "sequence"),
                "project_id": project_id,
                "order_status": safe_get(order, "order_status"),
                "survey_status": safe_get(order, "survey_status"),
                "date_confirmed": safe_get(order, "date_confirmed"),
                "courier_name": safe_get(order, "courier_name"),
                "tracking_code": safe_get(order, "tracking_code"),
                "email": safe_get(order, "email"),
                "paid_amount": safe_get(order, "paid_amount"),
                "credit_offer": safe_get(order, "credit_offer"),
                "balance": safe_get(order, "balance"),
                "recipient_name": nested_get(order, "shipping_address.name"),
                "country": nested_get(order, "shipping_address.country"),
                "country_code": nested_get(order, "shipping_address.country_code"),
                "state": nested_get(order, "shipping_address.state"),
                "city": nested_get(order, "shipping_address.city"),
                "zip": nested_get(order, "shipping_address.zip"),
                "address": nested_get(order, "shipping_address.address"),
                "address2": nested_get(order, "shipping_address.address2"),
                "phone": nested_get(order, "shipping_address.phone"),
                "raw_json": json_cell(order),
            }
        )
    return rows


def flatten_items_and_questions(
    orders: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    item_rows: list[dict[str, Any]] = []
    question_rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for order in orders:
        order_id = safe_get(order, "id")
        pbid = safe_get(order, "pbid")
        reward = order.get("reward") or {}
        if reward and not isinstance(reward, dict):
            errors.append(error_row("warning", "flatten_reward", None, order_id, pbid, "reward is not an object", reward))
            reward = {}

        reward_id = safe_get(reward, "id")
        reward_name = safe_get(reward, "name")
        reward_price = safe_get(reward, "price")

        append_questions(question_rows, order_id, pbid, "reward", "reward", reward_id, reward.get("questions"), reward)

        for item in ensure_list(reward.get("items")):
            if not isinstance(item, dict):
                errors.append(error_row("warning", "flatten_reward_item", None, order_id, pbid, "reward item is not an object", item))
                continue
            item_rows.append(item_row(order_id, pbid, "reward_item", reward_id, reward_name, reward_price, item, ""))
            append_questions(question_rows, order_id, pbid, "item", "reward_item", item.get("id"), item.get("questions"), item)

        for addon in ensure_list(order.get("addons")):
            if not isinstance(addon, dict):
                errors.append(error_row("warning", "flatten_addon", None, order_id, pbid, "addon is not an object", addon))
                continue
            item_rows.append(item_row(order_id, pbid, "addon", reward_id, reward_name, reward_price, addon, safe_get(addon, "price")))
            append_questions(question_rows, order_id, pbid, "item", "addon", addon.get("id"), addon.get("questions"), addon)

        for gift in ensure_list(order.get("gifts")):
            if not isinstance(gift, dict):
                errors.append(error_row("warning", "flatten_gift", None, order_id, pbid, "gift is not an object", gift))
                continue
            item_rows.append(item_row(order_id, pbid, "gift", reward_id, reward_name, reward_price, gift, ""))

    return item_rows, question_rows, errors


def item_row(
    order_id: Any,
    pbid: Any,
    item_source: str,
    reward_id: Any,
    reward_name: Any,
    reward_price: Any,
    item: dict[str, Any],
    price: Any,
) -> dict[str, Any]:
    return {
        "order_id": order_id,
        "pbid": pbid,
        "item_source": item_source,
        "reward_id": reward_id,
        "reward_name": reward_name,
        "reward_price": reward_price,
        "product_id": safe_get(item, "id"),
        "product_name": safe_get(item, "name"),
        "sku": safe_get(item, "sku"),
        "variant": json_cell(item.get("variant")),
        "quantity": safe_get(item, "number"),
        "price": price,
        "raw_json": json_cell(item),
    }


def append_questions(
    rows: list[dict[str, Any]],
    order_id: Any,
    pbid: Any,
    question_scope: str,
    item_source: str,
    product_id: Any,
    questions: Any,
    parent: Any,
) -> None:
    for question in ensure_list(questions):
        if isinstance(question, dict):
            rows.append(
                {
                    "order_id": order_id,
                    "pbid": pbid,
                    "question_scope": question_scope,
                    "item_source": item_source,
                    "product_id": product_id,
                    "question": first_present(question, ["question", "title", "name", "label"]),
                    "answer": first_present(question, ["answer", "value", "response"]),
                    "raw_json": json_cell(question),
                }
            )
        elif question not in (None, ""):
            rows.append(
                {
                    "order_id": order_id,
                    "pbid": pbid,
                    "question_scope": question_scope,
                    "item_source": item_source,
                    "product_id": product_id,
                    "question": "",
                    "answer": str(question),
                    "raw_json": json_cell({"parent": parent, "question": question}),
                }
            )


def first_present(data: dict[str, Any], keys: list[str]) -> Any:
    for key in keys:
        value = data.get(key)
        if value not in (None, ""):
            return value
    return ""


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def save_outputs(
    orders: list[dict[str, Any]],
    project_id: int,
    output_root: Path,
    is_completed: int | None,
    order_status: str,
    pages_requested: int,
    started_at: str,
    fetch_errors: list[dict[str, Any]],
) -> dict[str, Path | int]:
    finished_at = utc_now()
    output_dir = output_root / str(project_id)
    output_dir.mkdir(parents=True, exist_ok=True)

    raw_json_file = output_dir / f"raw_orders_{project_id}.json"
    orders_file = output_dir / f"orders_{project_id}.csv"
    items_file = output_dir / f"order_items_{project_id}.csv"
    questions_file = output_dir / f"questions_{project_id}.csv"
    summary_file = output_dir / f"run_summary_{project_id}.csv"
    errors_file = output_dir / f"errors_{project_id}.csv"

    order_rows = flatten_orders(orders, project_id)
    item_rows, question_rows, flatten_errors = flatten_items_and_questions(orders)
    error_rows = fetch_errors + flatten_errors

    with raw_json_file.open("w", encoding="utf-8") as handle:
        json.dump(orders, handle, ensure_ascii=False, indent=2)

    write_csv(orders_file, ORDER_FIELDS, order_rows)
    write_csv(items_file, ITEM_FIELDS, item_rows)
    write_csv(questions_file, QUESTION_FIELDS, question_rows)
    write_csv(errors_file, ERROR_FIELDS, error_rows)

    summary_rows = [
        {
            "project_id": project_id,
            "base_url": BASE_URL,
            "is_completed": "" if is_completed is None else is_completed,
            "order_status": order_status,
            "pages_requested": pages_requested,
            "orders_count": len(order_rows),
            "items_count": len(item_rows),
            "questions_count": len(question_rows),
            "errors_count": len(error_rows),
            "started_at": started_at,
            "finished_at": finished_at,
            "output_dir": str(output_dir),
            "raw_json_file": str(raw_json_file),
            "orders_file": str(orders_file),
            "order_items_file": str(items_file),
            "questions_file": str(questions_file),
            "errors_file": str(errors_file),
        }
    ]
    write_csv(summary_file, SUMMARY_FIELDS, summary_rows)

    return {
        "output_dir": output_dir,
        "raw_json_file": raw_json_file,
        "orders_file": orders_file,
        "order_items_file": items_file,
        "questions_file": questions_file,
        "summary_file": summary_file,
        "errors_file": errors_file,
        "orders_count": len(order_rows),
        "items_count": len(item_rows),
        "questions_count": len(question_rows),
        "errors_count": len(error_rows),
    }


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download PledgeBox orders and export raw JSON plus normalized CSV files.")
    parser.add_argument("--project-id", required=True, type=int, help="PledgeBox project ID.")
    parser.add_argument("--api-token", default=os.getenv("PLEDGEBOX_API_TOKEN"), help="PledgeBox API token. Defaults to PLEDGEBOX_API_TOKEN.")
    parser.add_argument("--is-completed", default=1, type=int, help="Use 1 to fetch completed survey orders. Defaults to 1.")
    parser.add_argument("--all-completion-statuses", action="store_true", help="Omit is_completed from the API request.")
    parser.add_argument("--order-status", default="lock", help="Order status filter: unlock, lock, shipped, or refunded. Defaults to lock.")
    parser.add_argument("--pb-id", default="", help="Optional PledgeBox ID filter for one order.")
    parser.add_argument("--email", default="", help="Optional email filter.")
    parser.add_argument("--output-dir", default="workspace/pledgebox_exports", help="Output root directory.")
    parser.add_argument("--max-pages", default=100, type=int, help="Maximum number of pages to request.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    api_token = compact_token(args.api_token)
    if not api_token:
        print("Missing API token. Use --api-token or set PLEDGEBOX_API_TOKEN.", file=sys.stderr)
        return 2
    if args.max_pages < 1:
        print("--max-pages must be at least 1.", file=sys.stderr)
        return 2

    started_at = utc_now()
    is_completed = None if args.all_completion_statuses else args.is_completed

    orders, pages_requested, fetch_errors = fetch_orders(
        api_token=api_token,
        project_id=args.project_id,
        is_completed=is_completed,
        order_status=args.order_status.strip(),
        max_pages=args.max_pages,
        pb_id=args.pb_id.strip(),
        email=args.email.strip(),
    )

    result = save_outputs(
        orders=orders,
        project_id=args.project_id,
        output_root=Path(args.output_dir),
        is_completed=is_completed,
        order_status=args.order_status.strip(),
        pages_requested=pages_requested,
        started_at=started_at,
        fetch_errors=fetch_errors,
    )

    print(json.dumps({key: str(value) for key, value in result.items()}, ensure_ascii=False, indent=2))
    return 1 if fetch_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
