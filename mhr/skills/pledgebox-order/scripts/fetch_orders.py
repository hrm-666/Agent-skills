from __future__ import annotations

import argparse
import json
from typing import Any

import requests

BASE_URL = "https://api.pledgebox.com/api/openapi/orders"
VALID_ORDER_STATUS = {"unlock", "lock", "shipped", "refunded"}


def fetch_orders(
    api_token: str,
    project_id: int,
    page: int = 1,
    is_completed: int | None = None,
    order_status: str | None = None,
    pb_id: str | None = None,
    email: str | None = None,
) -> dict[str, Any] | list[Any]:
    """从 PledgeBox 获取原始订单数据，不做清洗。"""
    if order_status and order_status not in VALID_ORDER_STATUS:
        raise ValueError(
            f"order_status must be one of: {', '.join(sorted(VALID_ORDER_STATUS))}"
        )

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

    response = requests.get(BASE_URL, params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch raw order data from PledgeBox API.")
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
    parser.add_argument("--pb_id", default=None, help="Specific PledgeBox order ID")
    parser.add_argument("--email", default=None, help="Specific backer email")
    args = parser.parse_args()

    data = fetch_orders(
        api_token=args.api_token,
        project_id=args.project_id,
        page=args.page,
        is_completed=args.is_completed,
        order_status=args.order_status,
        pb_id=args.pb_id,
        email=args.email,
    )
    print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
