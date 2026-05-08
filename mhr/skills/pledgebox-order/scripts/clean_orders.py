from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from openai import OpenAI

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from core.llm import PROVIDERS

API_CN_FIRST_PART_SPEC = """
获取订单信息
GET https://api.pledgebox.com/api/openapi/orders

响应参数：
- id: Number
- pbid: String
- ks_id: Number
- sequence: Number
- order_status: String
- survey_status: String
- date_confirmed: String
- courier_name: String
- tracking_code: String
- email: String
- shipping_address: Object
  - address: String
  - address2: String
  - city: String
  - state: String
  - zip: String
  - country: String
  - country_code: String
  - phone: String
  - name: String
- paid_amount: Number
- credit_offer: String
- balance: String
- reward: Object
  - id: Number
  - name: String
  - price: String
  - items: Array
    - id: Number
    - name: String
    - sku: String
    - variant: Array
    - number: Number
    - questions: Array
  - questions: Array
- addons: Array
  - id: Number
  - name: String
  - sku: String
  - price: String
  - variant: Array
  - number: Number
  - questions: Array
- gifts: Array
  - id: Number
  - name: String
  - sku: String
  - variant: Array
  - number: Number
""".strip()


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _load_schema() -> dict[str, Any]:
    schema_path = Path(__file__).resolve().parents[1] / "schema" / "cleaned_order_schema.json"
    return json.loads(schema_path.read_text(encoding="utf-8"))


def _load_runtime_config() -> tuple[str, str]:
    load_dotenv()
    env_provider = os.getenv("MINI_AGENT_ACTIVE_PROVIDER")
    env_model = os.getenv("MINI_AGENT_ACTIVE_MODEL")
    if env_provider and env_provider in PROVIDERS:
        return env_provider, env_model or PROVIDERS[env_provider]["default_model"]
    config_path = _repo_root() / "config.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8")) if config_path.exists() else {}
    provider = config.get("active_provider", "kimi")
    model = config.get("providers", {}).get(provider, {}).get("model") or PROVIDERS[provider]["default_model"]
    return provider, model


def _extract_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    try:
        data = json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("LLM did not return a JSON object")
        data = json.loads(stripped[start : end + 1])
    if not isinstance(data, dict):
        raise ValueError("LLM output is not a JSON object")
    return data


def _schema_type_names(value: Any) -> set[str]:
    if value is None:
        return {"null"}
    if isinstance(value, bool):
        return {"boolean"}
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return {"number"}
    if isinstance(value, str):
        return {"string"}
    if isinstance(value, list):
        return {"array"}
    if isinstance(value, dict):
        return {"object"}
    return {"unknown"}


def _validate_against_schema(data: Any, schema: dict[str, Any], path: str = "") -> list[str]:
    errors: list[str] = []
    expected_type = schema.get("type")
    expected_types = [expected_type] if isinstance(expected_type, str) else list(expected_type or [])
    actual_types = _schema_type_names(data)
    if expected_types and not actual_types.intersection(expected_types):
        errors.append(f"{path or '$'} type mismatch: expected {expected_types}, got {sorted(actual_types)}")
        return errors

    if isinstance(data, dict):
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        for key in required:
            if key not in data:
                errors.append(f"{path or '$'} missing required field: {key}")
        for key in data:
            if key not in properties:
                errors.append(f"{path or '$'} has extra field: {key}")
        for key, subschema in properties.items():
            if key in data:
                child_path = f"{path}.{key}" if path else key
                errors.extend(_validate_against_schema(data[key], subschema, child_path))
        return errors

    if isinstance(data, list):
        item_schema = schema.get("items")
        if item_schema:
            for index, item in enumerate(data):
                child_path = f"{path}[{index}]" if path else f"[{index}]"
                errors.extend(_validate_against_schema(item, item_schema, child_path))
    return errors


class LLMOrderCleaner:
    def __init__(self, provider: str | None = None, model: str | None = None):
        runtime_provider, runtime_model = _load_runtime_config()
        self.provider = provider or runtime_provider
        provider_meta = PROVIDERS[self.provider]
        self.model = model or runtime_model
        api_key = os.getenv(provider_meta["env_key"])
        if not api_key:
            raise RuntimeError(f"Missing environment variable: {provider_meta['env_key']}")
        self.client = OpenAI(api_key=api_key, base_url=provider_meta["base_url"])
        self.schema = _load_schema()

    def clean_order(self, raw_order: dict[str, Any]) -> dict[str, Any]:
        prompt = self._build_prompt(raw_order)
        last_errors: list[str] = []

        for attempt in range(3):
            content = self._complete(prompt, last_errors if attempt else None)
            cleaned = _extract_json_object(content)
            validation_errors = _validate_against_schema(cleaned, self.schema)
            if not validation_errors:
                return cleaned
            last_errors = validation_errors

        raise ValueError("LLM output failed schema validation: " + " | ".join(last_errors))

    def _build_prompt(self, raw_order: dict[str, Any]) -> str:
        return (
            "请根据下面给定的订单字段结构定义，对这条 PledgeBox 原始订单做清洗和分类。"
            "要求：\n"
            "1. 只能输出 schema 中允许的字段，禁止新增字段。\n"
            "2. 必须严格贴合下面给定的字段结构定义。\n"
            "3. 如果原始数据里使用 quantity 表示数量，请映射到输出字段 number。\n"
            "4. 原始数据里不属于给定字段结构的字段要忽略，不要输出。\n"
            "5. 缺失字段填 null，数组字段填 []。\n"
            "6. 只返回 JSON 对象，不要解释。\n\n"
            f"字段结构定义：\n{API_CN_FIRST_PART_SPEC}\n\n"
            f"目标 schema：\n{json.dumps(self.schema, ensure_ascii=False, indent=2)}\n\n"
            f"原始订单：\n{json.dumps(raw_order, ensure_ascii=False, indent=2)}"
        )

    def _complete(self, prompt: str, previous_errors: list[str] | None) -> str:
        user_prompt = prompt
        if previous_errors:
            user_prompt += (
                "\n\n上一次输出未通过校验，请修正这些问题后重新输出 JSON：\n- "
                + "\n- ".join(previous_errors)
            )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "你是一个严格的 JSON 数据清洗器。你只能输出符合约束的 JSON 对象。",
                    },
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
            )
        except Exception:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "你是一个严格的 JSON 数据清洗器。你只能输出符合约束的 JSON 对象。",
                    },
                    {"role": "user", "content": user_prompt},
                ],
            )
        return response.choices[0].message.content or ""


def _compare(raw_value: Any, cleaned_value: Any, raw_path: str, cleaned_path: str, diffs: list[dict[str, Any]]) -> None:
    if isinstance(raw_value, dict) and isinstance(cleaned_value, dict):
        raw_keys = set(raw_value.keys())
        cleaned_keys = set(cleaned_value.keys())

        for key in sorted(raw_keys - cleaned_keys):
            diffs.append(
                {
                    "type": "removed_field",
                    "raw_path": f"{raw_path}.{key}" if raw_path else key,
                    "cleaned_path": None,
                    "raw_value": raw_value.get(key),
                    "cleaned_value": None,
                }
            )
        for key in sorted(cleaned_keys - raw_keys):
            diffs.append(
                {
                    "type": "added_field",
                    "raw_path": None,
                    "cleaned_path": f"{cleaned_path}.{key}" if cleaned_path else key,
                    "raw_value": None,
                    "cleaned_value": cleaned_value.get(key),
                }
            )
        for key in sorted(raw_keys & cleaned_keys):
            next_raw_path = f"{raw_path}.{key}" if raw_path else key
            next_cleaned_path = f"{cleaned_path}.{key}" if cleaned_path else key
            _compare(raw_value.get(key), cleaned_value.get(key), next_raw_path, next_cleaned_path, diffs)
        return

    if isinstance(raw_value, list) and isinstance(cleaned_value, list):
        if len(raw_value) != len(cleaned_value):
            diffs.append(
                {
                    "type": "list_length_changed",
                    "raw_path": raw_path,
                    "cleaned_path": cleaned_path,
                    "raw_value": len(raw_value),
                    "cleaned_value": len(cleaned_value),
                }
            )
        for index, (raw_item, cleaned_item) in enumerate(zip(raw_value, cleaned_value)):
            _compare(raw_item, cleaned_item, f"{raw_path}[{index}]", f"{cleaned_path}[{index}]", diffs)
        for index in range(len(cleaned_value), len(raw_value)):
            diffs.append(
                {
                    "type": "removed_list_item",
                    "raw_path": f"{raw_path}[{index}]",
                    "cleaned_path": None,
                    "raw_value": raw_value[index],
                    "cleaned_value": None,
                }
            )
        for index in range(len(raw_value), len(cleaned_value)):
            diffs.append(
                {
                    "type": "added_list_item",
                    "raw_path": None,
                    "cleaned_path": f"{cleaned_path}[{index}]",
                    "raw_value": None,
                    "cleaned_value": cleaned_value[index],
                }
            )
        return

    if raw_value != cleaned_value:
        diffs.append(
            {
                "type": "value_changed",
                "raw_path": raw_path,
                "cleaned_path": cleaned_path,
                "raw_value": raw_value,
                "cleaned_value": cleaned_value,
            }
        )


def build_diff_log(raw_order: dict[str, Any], cleaned_order: dict[str, Any]) -> dict[str, Any]:
    diffs: list[dict[str, Any]] = []
    _compare(raw_order, cleaned_order, "", "", diffs)
    return {
        "pbid": raw_order.get("pbid"),
        "difference_count": len(diffs),
        "differences": diffs,
    }


def clean_orders(
    raw_orders: Any,
    provider: str | None = None,
    model: str | None = None,
    cleaner: LLMOrderCleaner | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not isinstance(raw_orders, list):
        raise ValueError("raw_orders must be a list")

    order_cleaner = cleaner or LLMOrderCleaner(provider=provider, model=model)
    cleaned_orders: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for raw_order in raw_orders:
        try:
            cleaned_order = order_cleaner.clean_order(raw_order)
            cleaned_orders.append(cleaned_order)
            errors.append(build_diff_log(raw_order, cleaned_order))
        except Exception as exc:
            errors.append(
                {
                    "pbid": raw_order.get("pbid") if isinstance(raw_order, dict) else None,
                    "error": str(exc),
                    "raw_order": raw_order,
                }
            )

    return cleaned_orders, errors
