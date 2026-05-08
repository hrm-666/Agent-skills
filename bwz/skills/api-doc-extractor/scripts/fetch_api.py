from __future__ import annotations

import json
import socket
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "Mini-Agent/api-doc-extractor",
}


@dataclass
class FetchResult:
    attempted: bool
    ok: bool
    skipped_reason: str | None = None
    status_code: int | None = None
    content_type: str | None = None
    byte_count: int = 0
    json_ok: bool = False
    response_shape: dict[str, Any] | None = None
    raw_response_paths: list[str] | None = None
    error: str | None = None
    warnings: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "attempted": self.attempted,
            "ok": self.ok,
            "skipped_reason": self.skipped_reason,
            "status_code": self.status_code,
            "content_type": self.content_type,
            "byte_count": self.byte_count,
            "json_ok": self.json_ok,
            "response_shape": self.response_shape,
            "raw_response_paths": self.raw_response_paths or [],
            "error": self.error,
            "warnings": self.warnings or [],
        }


def fetch_from_plan(
    request_plan: dict[str, Any],
    *,
    timeout: int,
    output_root: Path,
) -> FetchResult:
    method = request_plan.get("method")
    request_url = request_plan.get("request_url")
    missing_required = request_plan.get("missing_required_params") or []

    if method != "GET":
        return FetchResult(
            attempted=False,
            ok=False,
            skipped_reason="only_get_requests_are_executed",
            warnings=["side_effecting_request_not_executed"],
        )
    if missing_required:
        return FetchResult(
            attempted=False,
            ok=False,
            skipped_reason="missing_required_params",
            warnings=[f"missing_required_params:{','.join(missing_required)}"],
        )
    if not request_url:
        return FetchResult(
            attempted=False,
            ok=False,
            skipped_reason="missing_request_url",
            warnings=["missing_request_url"],
        )

    raw_dir = output_root / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    try:
        return fetch_get(request_url, timeout=timeout, raw_dir=raw_dir)
    except HTTPError as exc:
        body = exc.read()
        raw_path = save_raw_response(raw_dir, body, suffix=response_suffix(exc.headers.get("Content-Type")))
        return FetchResult(
            attempted=True,
            ok=False,
            status_code=exc.code,
            content_type=exc.headers.get("Content-Type"),
            byte_count=len(body),
            json_ok=is_json_bytes(body),
            response_shape=summarize_json_bytes(body),
            raw_response_paths=[str(raw_path)],
            error=f"HTTP {exc.code} {exc.reason}",
            warnings=["http_error"],
        )
    except (URLError, TimeoutError, socket.timeout) as exc:
        return FetchResult(
            attempted=True,
            ok=False,
            error=str(exc),
            warnings=["request_failed"],
        )


def fetch_get(request_url: str, *, timeout: int, raw_dir: Path) -> FetchResult:
    request = Request(request_url, headers=DEFAULT_HEADERS, method="GET")
    with urlopen(request, timeout=timeout) as response:
        body = response.read()
        status_code = response.getcode()
        content_type = response.headers.get("Content-Type")

    raw_path = save_raw_response(raw_dir, body, suffix=response_suffix(content_type))
    json_data = parse_json_bytes(body)
    return FetchResult(
        attempted=True,
        ok=200 <= status_code < 300,
        status_code=status_code,
        content_type=content_type,
        byte_count=len(body),
        json_ok=json_data is not None,
        response_shape=summarize_json(json_data) if json_data is not None else None,
        raw_response_paths=[str(raw_path)],
        warnings=[] if json_data is not None else ["non_json_response"],
    )


def save_raw_response(raw_dir: Path, body: bytes, *, suffix: str) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = raw_dir / f"api-response-{timestamp}{suffix}"
    path.write_bytes(body)
    return path


def response_suffix(content_type: str | None) -> str:
    if content_type and "json" in content_type.lower():
        return ".json"
    return ".txt"


def parse_json_bytes(body: bytes) -> Any | None:
    try:
        return json.loads(body.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None


def is_json_bytes(body: bytes) -> bool:
    return parse_json_bytes(body) is not None


def summarize_json_bytes(body: bytes) -> dict[str, Any] | None:
    data = parse_json_bytes(body)
    return summarize_json(data) if data is not None else None


def summarize_json(data: Any) -> dict[str, Any]:
    if isinstance(data, list):
        return {
            "root_type": "array",
            "item_count": len(data),
            "top_level_keys": [],
            "main_array_path": "$",
        }
    if isinstance(data, dict):
        main_path, item_count = find_main_array(data)
        return {
            "root_type": "object",
            "item_count": item_count,
            "top_level_keys": list(data.keys())[:30],
            "main_array_path": main_path,
        }
    return {
        "root_type": type(data).__name__,
        "item_count": None,
        "top_level_keys": [],
        "main_array_path": None,
    }


def find_main_array(data: dict[str, Any]) -> tuple[str | None, int | None]:
    preferred = ("data", "items", "list", "orders", "records", "results", "rows")
    for key in preferred:
        value = data.get(key)
        if isinstance(value, list):
            return key, len(value)
        if isinstance(value, dict):
            nested_path, nested_count = find_main_array(value)
            if nested_path is not None:
                return f"{key}.{nested_path}", nested_count
    return None, None
