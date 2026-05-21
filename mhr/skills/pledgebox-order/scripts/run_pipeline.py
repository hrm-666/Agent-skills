from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from clean_orders import LLMOrderCleaner, build_diff_log
from fetch_orders import VALID_ORDER_STATUS, fetch_orders


def ensure_output_dir(output_dir: str) -> Path:
    """确保输出目录存在。"""
    path = Path(output_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_json(data: Any, path: Path) -> None:
    """将数据保存为 JSON。"""
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def save_progress(progress: dict[str, Any], output_dir: Path) -> None:
    """保存当前进度，供网页端轮询展示。"""
    save_json(progress, output_dir / "progress.json")


def extract_order_list(raw_response: Any) -> list[Any]:
    """把不同形态的 API 响应统一抽成订单列表。"""
    if isinstance(raw_response, list):
        return raw_response

    if isinstance(raw_response, dict):
        data = raw_response.get("data")
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return [data]
        if "pbid" in raw_response:
            return [raw_response]

    return []


def fetch_all_orders(
    api_token: str,
    project_id: int,
    start_page: int = 1,
    is_completed: int | None = None,
    order_status: str | None = None,
    pb_id: str | None = None,
    email: str | None = None,
) -> dict[str, Any]:
    """自动翻页抓取订单，直到取完全部数据或遇到空页。"""
    first_response = fetch_orders(
        api_token=api_token,
        project_id=project_id,
        page=start_page,
        is_completed=is_completed,
        order_status=order_status,
        pb_id=pb_id,
        email=email,
    )

    first_page_orders = extract_order_list(first_response)
    if not isinstance(first_response, dict):
        return {"code": 200, "total_count": len(first_page_orders), "data": first_page_orders}

    total_count = first_response.get("total_count")
    if not isinstance(total_count, int):
        total_count = len(first_page_orders)

    all_orders = list(first_page_orders)
    page = start_page + 1

    while len(all_orders) < total_count:
        next_response = fetch_orders(
            api_token=api_token,
            project_id=project_id,
            page=page,
            is_completed=is_completed,
            order_status=order_status,
            pb_id=pb_id,
            email=email,
        )
        next_orders = extract_order_list(next_response)
        if not next_orders:
            break
        all_orders.extend(next_orders)
        page += 1

    merged_response = dict(first_response)
    merged_response["data"] = all_orders
    merged_response["total_count"] = total_count
    merged_response["fetched_pages"] = page - start_page
    merged_response["fetched_count"] = len(all_orders)
    return merged_response


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fetch and clean PledgeBox order data.")
    parser.add_argument("--api_token", required=True, help="PledgeBox API token")
    parser.add_argument("--project_id", required=True, type=int, help="PledgeBox project ID")
    parser.add_argument("--page", default=1, type=int, help="Page number")
    parser.add_argument("--is_completed", type=int, choices=[0, 1], default=None, help="1 for completed orders")
    parser.add_argument(
        "--order_status",
        default=None,
        choices=sorted(VALID_ORDER_STATUS),
        help="unlock / lock / shipped / refunded",
    )
    parser.add_argument("--pb_id", default=None, help="Specific PledgeBox ID")
    parser.add_argument("--email", default=None, help="Specific backer email")
    parser.add_argument(
        "--all_pages",
        action="store_true",
        help="Fetch all pages instead of only one page",
    )
    parser.add_argument(
        "--output_dir",
        default="workspace/pledgebox-order-output",
        help="Directory for raw/cleaned JSON outputs",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    output_dir = ensure_output_dir(args.output_dir)
    raw_output_path = output_dir / "raw_orders.json"
    cleaned_output_path = output_dir / "cleaned_orders.json"
    error_output_path = output_dir / "error_log.json"

    save_progress(
        {
            "stage": "fetching_raw",
            "message": "正在拉取原始订单数据",
            "processed": 0,
            "total": 0,
            "cleaned": 0,
            "errors": 0,
        },
        output_dir,
    )

    should_fetch_all_pages = args.all_pages and not args.pb_id and not args.email
    if should_fetch_all_pages:
        raw_response = fetch_all_orders(
            api_token=args.api_token,
            project_id=args.project_id,
            start_page=args.page,
            is_completed=args.is_completed,
            order_status=args.order_status,
            pb_id=args.pb_id,
            email=args.email,
        )
    else:
        raw_response = fetch_orders(
            api_token=args.api_token,
            project_id=args.project_id,
            page=args.page,
            is_completed=args.is_completed,
            order_status=args.order_status,
            pb_id=args.pb_id,
            email=args.email,
        )

    save_json(raw_response, raw_output_path)

    raw_orders = extract_order_list(raw_response)
    total_orders = len(raw_orders)
    save_progress(
        {
            "stage": "raw_saved",
            "message": "原始订单已保存，开始逐条清洗",
            "processed": 0,
            "total": total_orders,
            "cleaned": 0,
            "errors": 0,
            "raw_output_path": str(raw_output_path),
        },
        output_dir,
    )

    cleaned_orders: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    cleaner = LLMOrderCleaner()

    save_json(cleaned_orders, cleaned_output_path)
    save_json(errors, error_output_path)

    for index, raw_order in enumerate(raw_orders, start=1):
        pbid = raw_order.get("pbid") if isinstance(raw_order, dict) else None
        try:
            cleaned_order = cleaner.clean_order(raw_order)
            cleaned_orders.append(cleaned_order)
            errors.append(build_diff_log(raw_order, cleaned_order))
            progress_message = f"正在清洗第 {index}/{total_orders} 条订单"
        except Exception as exc:
            errors.append(
                {
                    "pbid": pbid,
                    "error": str(exc),
                    "raw_order": raw_order,
                }
            )
            progress_message = f"第 {index}/{total_orders} 条订单清洗失败"

        save_json(cleaned_orders, cleaned_output_path)
        save_json(errors, error_output_path)
        save_progress(
            {
                "stage": "cleaning",
                "message": progress_message,
                "processed": index,
                "total": total_orders,
                "cleaned": len(cleaned_orders),
                "errors": sum(1 for item in errors if "error" in item),
                "current_pbid": pbid,
                "raw_output_path": str(raw_output_path),
                "cleaned_output_path": str(cleaned_output_path),
                "error_output_path": str(error_output_path),
            },
            output_dir,
        )
        print(f"[PROGRESS] {progress_message} cleaned={len(cleaned_orders)} errors={sum(1 for item in errors if 'error' in item)}")

    save_progress(
        {
            "stage": "completed",
            "message": "全部订单处理完成",
            "processed": total_orders,
            "total": total_orders,
            "cleaned": len(cleaned_orders),
            "errors": sum(1 for item in errors if "error" in item),
            "raw_output_path": str(raw_output_path),
            "cleaned_output_path": str(cleaned_output_path),
            "error_output_path": str(error_output_path),
        },
        output_dir,
    )

    print("[DONE] PledgeBox order pipeline finished.")
    print(f"Raw data saved to: {raw_output_path}")
    print(f"Cleaned data saved to: {cleaned_output_path}")
    print(f"Error log saved to: {error_output_path}")
    if isinstance(raw_response, dict) and "fetched_pages" in raw_response:
        print(f"Fetched pages: {raw_response['fetched_pages']}")
        print(f"Fetched count: {raw_response.get('fetched_count', len(raw_orders))}")
    print(f"Total raw orders: {len(raw_orders)}")
    print(f"Total cleaned orders: {len(cleaned_orders)}")
    print(f"Total errors: {sum(1 for item in errors if 'error' in item)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
