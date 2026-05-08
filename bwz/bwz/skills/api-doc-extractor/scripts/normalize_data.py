from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PREFERRED_ARRAY_KEYS = ("data", "items", "list", "orders", "records", "results", "rows")


@dataclass
class NormalizeResult:
    ok: bool
    items_count: int
    main_array_path: str | None
    fields_used: list[str]
    records: list[dict[str, str]]
    warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        preview = self.records[:20]
        return {
            "ok": self.ok,
            "items_count": self.items_count,
            "main_array_path": self.main_array_path,
            "fields_used": self.fields_used,
            "records_preview": preview,
            "preview_count": len(preview),
            "warnings": self.warnings,
        }


def normalize_from_raw_response(
    raw_response_path: str | Path,
    response_fields: list[dict[str, Any]] | None = None,
) -> NormalizeResult:
    path = Path(raw_response_path)
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    items, main_array_path = locate_main_items(data)
    field_paths = collect_field_paths(response_fields or [], items)
    records = [normalize_record(item, field_paths) for item in items]
    warnings: list[str] = []
    if not field_paths:
        warnings.append("no_fields_selected")
    if not items:
        warnings.append("no_items_found")
    return NormalizeResult(
        ok=True,
        items_count=len(items),
        main_array_path=main_array_path,
        fields_used=field_paths,
        records=records,
        warnings=warnings,
    )


def locate_main_items(data: Any) -> tuple[list[Any], str | None]:
    if isinstance(data, list):
        return data, "$"
    if isinstance(data, dict):
        path, items = find_main_array(data)
        if items is not None:
            return items, path
        return [data], None
    return [{"value": data}], None


def find_main_array(data: dict[str, Any], prefix: str = "") -> tuple[str | None, list[Any] | None]:
    for key in PREFERRED_ARRAY_KEYS:
        value = data.get(key)
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, list):
            return path, value
        if isinstance(value, dict):
            nested_path, nested_items = find_main_array(value, prefix=path)
            if nested_items is not None:
                return nested_path, nested_items
    return None, None


def collect_field_paths(response_fields: list[dict[str, Any]], items: list[Any]) -> list[str]:
    paths: list[str] = []
    for field in response_fields:
        path = str(field.get("path", "")).strip()
        field_type = str(field.get("type", "")).strip()
        if not path:
            continue
        if field_type in {"Object", "Array"}:
            continue
        paths.append(path)
    if paths:
        return dedupe(paths)

    if items and isinstance(items[0], dict):
        return sorted(flatten_available_paths(items[0]))
    return []


def flatten_available_paths(value: Any, prefix: str = "") -> set[str]:
    paths: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            child_prefix = f"{prefix}.{key}" if prefix else key
            if isinstance(item, dict):
                paths.update(flatten_available_paths(item, child_prefix))
            elif isinstance(item, list):
                if item and all(not isinstance(element, (dict, list)) for element in item):
                    paths.add(f"{child_prefix}[]")
                elif item and isinstance(item[0], dict):
                    for nested in flatten_available_paths(item[0], f"{child_prefix}[]"):
                        paths.add(nested)
                else:
                    paths.add(f"{child_prefix}[]")
            else:
                paths.add(child_prefix)
    return paths


def normalize_record(item: Any, field_paths: list[str]) -> dict[str, str]:
    if not field_paths and isinstance(item, dict):
        return {key: stringify_scalar(value) for key, value in item.items() if not isinstance(value, (dict, list))}

    normalized: dict[str, str] = {}
    for path in field_paths:
        values = extract_path_values(item, path)
        normalized[path] = join_values(values)
    return normalized


def extract_path_values(value: Any, path: str) -> list[Any]:
    segments = split_path(path)
    return walk_segments(value, segments)


def split_path(path: str) -> list[str]:
    segments = [segment for segment in path.split(".") if segment]
    return segments


def walk_segments(value: Any, segments: list[str]) -> list[Any]:
    if not segments:
        return [value]
    if value is None:
        return []

    segment = segments[0]
    rest = segments[1:]
    is_array = segment.endswith("[]")
    key = segment[:-2] if is_array else segment

    if isinstance(value, dict):
        next_value = value.get(key)
        if is_array:
            if not isinstance(next_value, list):
                return []
            results: list[Any] = []
            for item in next_value:
                results.extend(walk_segments(item, rest))
            return results
        return walk_segments(next_value, rest)

    if isinstance(value, list):
        results: list[Any] = []
        for item in value:
            results.extend(walk_segments(item, segments))
        return results

    return []


def join_values(values: list[Any]) -> str:
    scalars = [stringify_scalar(value) for value in values if value is not None]
    scalars = [value for value in scalars if value != ""]
    if not scalars:
        return ""
    return "; ".join(dedupe(scalars))


def stringify_scalar(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (str, int, float)):
        return str(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result
