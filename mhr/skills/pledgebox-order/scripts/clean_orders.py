from __future__ import annotations

from typing import Any


def clean_variant(value: Any) -> list[Any] | dict[str, Any]:
    """保留原始 variant 结构，避免对象型变体被误清空。"""
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return value
    return []


def clean_items(items: Any) -> list[dict[str, Any]]:
    """清洗 reward、addon、gift 下的产品列表。"""
    if not isinstance(items, list):
        return []

    cleaned_items: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        cleaned_items.append(
            {
                "id": item.get("id"),
                "name": item.get("name"),
                "sku": item.get("sku"),
                "price": item.get("price"),
                "variant": clean_variant(item.get("variant")),
                "number": item.get("number"),
                "questions": item.get("questions") if isinstance(item.get("questions"), list) else [],
                "items": clean_items(item.get("items", [])),
            }
        )
    return cleaned_items


def clean_order(raw_order: dict[str, Any]) -> dict[str, Any]:
    """把单条 PledgeBox 原始订单清洗成统一结构。"""
    if not isinstance(raw_order, dict):
        raise ValueError("raw_order must be a dict")

    shipping_address = raw_order.get("shipping_address") or {}
    reward = raw_order.get("reward") or {}

    return {
        "id": raw_order.get("id"),
        "source": raw_order.get("source"),
        "pbid": raw_order.get("pbid"),
        "ks_id": raw_order.get("ks_id"),
        "sequence": raw_order.get("sequence"),
        "email": raw_order.get("email"),
        "order_status": raw_order.get("order_status"),
        "order_status_normalized": (
            str(raw_order.get("order_status")).lower() if raw_order.get("order_status") is not None else None
        ),
        "survey_status": raw_order.get("survey_status"),
        "date_confirmed": raw_order.get("date_confirmed"),
        "courier_name": raw_order.get("courier_name"),
        "tracking_code": raw_order.get("tracking_code"),
        "shipping_amount": raw_order.get("shipping_amount"),
        "tax": raw_order.get("tax"),
        "value_added_tax": raw_order.get("value_added_tax"),
        "custom_duty": raw_order.get("custom_duty"),
        "tariff": raw_order.get("tariff"),
        "shipping_address": {
            "name": shipping_address.get("name"),
            "phone": shipping_address.get("phone"),
            "address": shipping_address.get("address"),
            "address2": shipping_address.get("address2"),
            "city": shipping_address.get("city"),
            "state": shipping_address.get("state"),
            "zip": shipping_address.get("zip"),
            "country": shipping_address.get("country"),
            "country_code": shipping_address.get("country_code"),
        },
        "payment": {
            "paid_amount": raw_order.get("paid_amount"),
            "credit_offer": raw_order.get("credit_offer"),
            "balance": raw_order.get("balance"),
        },
        "date_invited": raw_order.get("date_invited"),
        "date_completed": raw_order.get("date_completed"),
        "is_dropped": raw_order.get("is_dropped"),
        "note": raw_order.get("note"),
        "reward": {
            "id": reward.get("id"),
            "name": reward.get("name"),
            "price": reward.get("price"),
            "items": clean_items(reward.get("items", [])),
            "questions": reward.get("questions") if isinstance(reward.get("questions"), list) else [],
        },
        "addons": clean_items(raw_order.get("addons", [])),
        "gifts": clean_items(raw_order.get("gifts", [])),
    }


def clean_orders(raw_orders: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """批量清洗订单，并记录失败项。"""
    if not isinstance(raw_orders, list):
        raise ValueError("raw_orders must be a list")

    cleaned_orders: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for raw_order in raw_orders:
        try:
            cleaned_orders.append(clean_order(raw_order))
        except Exception as exc:
            errors.append(
                {
                    "pbid": raw_order.get("pbid") if isinstance(raw_order, dict) else None,
                    "error": str(exc),
                    "raw_order": raw_order,
                }
            )

    return cleaned_orders, errors
