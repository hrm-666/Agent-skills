#!/usr/bin/env python3
"""
API Extractor — 从 API 文档中提取 GET 接口、访问并整理数据。

用法:
  python run.py --doc <path> [--format markdown|csv|json] [--dry-run] [--timeout 30]
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

# ── 常量 ──────────────────────────────────────────────────
USER_AGENT = "Mini-Agent/api-extractor"
SENSITIVE_KEYS = {"api_token", "token", "access_token", "api_key", "secret", "password"}
MAIN_ARRAY_KEYS = ("data", "items", "list", "orders", "records", "results", "rows")
SUPPORTED_SUFFIXES = {".pdf", ".md", ".txt", ".markdown"}

# ── 第 1 步：文本提取 ──────────────────────────────────────


def extract_text(doc_path: Path) -> str:
    """从 PDF / Markdown / TXT 提取纯文本。"""
    suffix = doc_path.suffix.lower()
    if suffix == ".pdf":
        return _extract_pdf(doc_path)
    if suffix in {".md", ".txt", ".markdown"}:
        return doc_path.read_text(encoding="utf-8", errors="replace")
    raise ValueError(f"不支持的文件格式：{suffix}，支持：{', '.join(SUPPORTED_SUFFIXES)}")


def _extract_pdf(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        try:
            from PyPDF2 import PdfReader
        except ImportError:
            raise ImportError("需要安装 pypdf：pip install pypdf")

    reader = PdfReader(str(path))
    pages = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages.append(text)
    if not pages:
        raise ValueError("PDF 无可提取的文本，可能是扫描件（不支持 OCR）")
    return "\n".join(pages)


# ── 第 2 步：接口解析 ──────────────────────────────────────

def parse_api_doc(text: str) -> dict:
    """解析文本，提取 GET 接口信息。"""
    # 合并被换行拆开的 URL 片段
    text = _join_broken_urls(text)

    # 找所有方法行（GET/POST/PUT/DELETE + URL）
    method_pattern = re.compile(
        r'(GET|POST|PUT|PATCH|DELETE)\s+(https?://[^\s\n]+)',
        re.IGNORECASE,
    )
    matches = list(method_pattern.finditer(text))
    interfaces = []

    for i, m in enumerate(matches):
        method = m.group(1).upper()
        endpoint_url = m.group(2).strip()

        # 向前找标题
        before = text[: m.start()]
        title = _find_title_before(before)

        # 限定 scope：当前方法行到下一个方法行之间（或文本末尾）
        next_start = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        scope = text[m.end():next_start]

        params = _parse_param_table(scope, endpoint_url, method)
        response_fields = _parse_response_fields(scope)

        request_url, missing = _build_request_url(endpoint_url, params)

        interfaces.append({
            "title": title,
            "method": method,
            "endpoint_url": endpoint_url,
            "request_url": request_url,
            "params": params,
            "missing_required_params": missing,
            "response_fields": response_fields,
        })

    # 优先选第一个 GET 接口
    get_ifaces = [i for i in interfaces if i["method"] == "GET"]
    selected = get_ifaces[0] if get_ifaces else (interfaces[0] if interfaces else None)

    if not selected:
        return {"interfaces": interfaces, "selected": None, "error": "未找到 API 接口"}

    return {
        "interfaces": interfaces,
        "interfaces_count": len(interfaces),
        "selected": selected,
    }


def _join_broken_urls(text: str) -> str:
    """拼接被 PDF 换行拆开的 URL。"""
    # 以 http 开头的行，后续行如果只含 URL 字符则拼接
    lines = text.split("\n")
    result = []
    i = 0
    while i < len(lines):
        line = lines[i]
        result.append(line)
        if re.match(r'^\s*(GET|POST|PUT|PATCH|DELETE)\s+https?://', line, re.IGNORECASE):
            # 后续行如果像 URL 片段则拼接到当前行
            while i + 1 < len(lines):
                next_line = lines[i + 1]
                if re.match(r'^[A-Za-z0-9\-._~:/?#\[\]@!$&\'()*+,;=%]+$', next_line.strip()):
                    result[-1] = result[-1].rstrip() + next_line.strip()
                    i += 1
                else:
                    break
        i += 1
    return "\n".join(result)


def _find_title_before(text_before: str) -> str:
    """在方法行之前的文本中找标题（逆向找最近的非 URL 短文本行）。"""
    lines = [l.strip() for l in text_before.split("\n") if l.strip()]
    for line in reversed(lines):
        # 跳过 URL、表头、分隔线
        if re.match(r'^https?://', line):
            continue
        if re.match(r'^[-=|]+$', line):
            continue
        if re.match(r'^(参数名|名称|字段名|参数|字段|Name|Field|Parameter)', line, re.IGNORECASE):
            continue
        # 标题通常短且不含过多特殊字符
        if len(line) <= 60 and not re.search(r'[<>{}]', line):
            return line
    return "未命名接口"


def _parse_param_table(text: str, endpoint_url: str = "", method: str = "") -> list[dict]:
    """Parse request parameter table. Encoding-agnostic — does not rely on Chinese keywords.

    Tries bare params first (most common for PDF-extracted APIs), falls back to
    table-based parsing only when bare params find nothing.
    """
    # Primary: bare param lines (work for most GET endpoints)
    bare_params = _parse_params_bare(text)
    if bare_params:
        return bare_params

    # Fallback: table with header (e.g., POST endpoints with type columns)
    table_start = _find_table_start(text)
    if table_start is not None:
        return _parse_params_with_header(text, table_start)

    return []


def _parse_params_with_header(text: str, start: int) -> list[dict]:
    """Parse params from a table with header row."""
    params = []
    table_text = text[start:]
    lines = table_text.split("\n")
    header_line = lines[0].strip()
    schema = _detect_param_schema(header_line)

    for line in lines[1:]:
        stripped = line.strip()
        if not stripped:
            break
        if re.match(r'^[-=|]{3,}$', stripped):
            break
        # Stop at next URL, HTTP method, JSON, or section-like line
        if re.match(r'^(https?://|\{|\}|\[|\]|GET|POST|PUT|PATCH|DELETE)\s', stripped):
            break

        indent = len(line) - len(line.lstrip())
        parts = _split_table_line(stripped)
        if len(parts) < 2:
            continue

        param = _build_param(parts, indent, schema)
        if param:
            params.append(param)

    return params


def _parse_params_bare(text: str) -> list[dict]:
    """Encoding-agnostic bare param parsing. Each param line: identifier word rest."""
    params = []
    # Move past the method+URL line
    m = re.search(r'(GET|POST|PUT|PATCH|DELETE)\s+https?://[^\n]+', text, re.IGNORECASE)
    start = m.end() if m else 0
    scope = text[start:]

    for line in scope.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        # Stop conditions (encoding-agnostic)
        if re.match(r'^https?://', stripped):
            break
        if re.match(r'^(GET|POST|PUT|PATCH|DELETE)\s', stripped):
            break
        if stripped.startswith('{') or stripped.startswith('['):
            break

        # Param pattern: identifier_word non_space_word rest_of_description
        m = re.match(r'([a-zA-Z_]\w*)\s+(\S+)\s+(.*)', stripped)
        if m:
            name = m.group(1)
            second = m.group(2)
            desc = m.group(3).strip()

            # second word could be a garbled "required/optional" indicator
            # or a type like "String"/"Number". Check if it matches a known type.
            if _is_type(second):
                # This line has a type column (like table-format params)
                is_opt = "optional" in desc.lower() or "option" in desc.lower() or "选填" in desc
                params.append({
                    "name": name,
                    "indent": 0,
                    "type": second,
                    "required": not is_opt,
                    "description": desc,
                    "value": _extract_value_ascii(desc),
                })
            else:
                # Garbled indicator — check for Chinese UTF-8 bytes directly
                # (terminal may show mojibake but bytes are correct)
                is_req = "必填" in second or "required" in second.lower()
                is_opt = "选填" in second or "optional" in second.lower() or "option" in second.lower()
                params.append({
                    "name": name,
                    "indent": 0,
                    "required": is_req or not is_opt,
                    "description": desc,
                    "value": _extract_value_ascii(desc),
                })

    return params


def _split_table_line(line: str) -> list[str]:
    """Split a table row into columns. Tries multiple delimiters."""
    if '|' in line:
        return [p.strip() for p in line.split('|') if p.strip()]
    if '\t' in line:
        return [p.strip() for p in line.split('\t') if p.strip()]
    # Multiple spaces
    parts = re.split(r'\s{2,}', line)
    if len(parts) >= 2:
        return parts
    # Single-space fallback: identifier word rest
    m = re.match(r'([a-zA-Z_]\w*)\s+(\S+)\s+(.*)', line)
    if m:
        return [m.group(1), m.group(2), m.group(3)]
    return [line]


def _build_param(parts: list[str], indent: int, schema: str) -> dict | None:
    """从分割后的列构建参数字典。"""
    name = parts[0].strip()
    if not name or len(parts) < 2:
        return None

    param = {"name": name, "indent": indent}
    col = 1

    if schema == "name_type_required_desc":
        if len(parts) > col:
            param["type"] = parts[col].strip()
            col += 1

    if len(parts) > col:
        req_text = parts[col].strip()
        # Check Chinese UTF-8 bytes directly (terminal may show mojibake)
        is_req = "必填" in req_text or "required" in req_text.lower()
        is_opt = "选填" in req_text or "optional" in req_text.lower() or "option" in req_text.lower()
        param["required"] = is_req or not is_opt
        col += 1

    param["description"] = parts[col].strip() if len(parts) > col else ""
    param["value"] = _extract_value_from_description(param["description"]) if param["description"] else None

    return param


def _detect_param_schema(header: str) -> str:
    """检测参数表的列 schema。"""
    header_lower = header.lower()
    has_type = any(t in header_lower for t in ("类型", "type"))
    return "name_type_required_desc" if has_type else "name_required_desc"


def _extract_value_from_description(desc: str) -> str | None:
    """Extract default value from parameter description.

    Handles patterns like 'project_id：100001', 'default page = 1'.
    Uses both fullwidth and ASCII separators.
    """
    # Match value after colon or equals
    for pat in [r'[：:]\s*(\S+)', r'=\s*(\S+)', r'default\s+(\S+)']:
        m = re.search(pat, desc, re.IGNORECASE)
        if m:
            val = m.group(1).rstrip(',;.)')
            # Skip if it looks like a descriptive word, not a value
            if val.lower() not in {"是", "否", "可选", "必填", "true", "false",
                                     "number", "string", "array", "object"}:
                return val
    return None


def _extract_value_ascii(desc: str) -> str | None:
    """Extract default value from description (ASCII patterns only).

    Handles: 'default page = 1', 'project_id: 100001', etc.
    """
    for pat in [r'=\s*(\S+)', r':\s*(\S+)']:
        m = re.search(pat, desc)
        if m:
            val = m.group(1).rstrip(',;.)')
            if val.lower() not in {"true", "false", "number", "string", "array", "object"}:
                return val
    # Look for numbers or IDs
    m = re.search(r'\b(\d{4,})\b', desc)  # likely an ID
    if m:
        return m.group(1)
    return None


def _find_table_start(text: str) -> int | None:
    """Locate the start of a table. Returns char offset or None.

    Encoding-agnostic: uses type-word detection on potential column 2.
    """
    lines = text.split("\n")
    offset = 0
    KNOWN_HEADERS = {"参数名", "参数", "名称", "name", "parameter", "field", "字段",
                     "字段名", "参数名称", "params", "parameters"}

    for i, line in enumerate(lines):
        lowered = line.strip().lower()

        if not lowered or lowered.startswith("#"):
            offset += len(line) + 1
            continue

        # Strategy 1: known header keywords (multispace / pipe / tab split)
        for h in KNOWN_HEADERS:
            if h.lower() in lowered:
                parts = re.split(r'\s{2,}|\t|\|', line.strip())
                if len(parts) >= 2:
                    return offset

        # Strategy 2: try all split methods and check if column 2 is a type
        parts = _split_cells(line.strip())
        if len(parts) >= 2 and _is_type(parts[1]):
            # Verify: next line should have same structure
            if i + 1 < len(lines):
                next_parts = _split_cells(lines[i + 1].strip())
                if len(next_parts) >= 2 and _is_type(next_parts[1]):
                    return offset

        offset += len(line) + 1

    return None


def _split_cells(line: str) -> list[str]:
    """Split a table row into cells, trying multiple delimiters."""
    for pat in [r'\s{2,}', r'\t', r'\|']:
        parts = re.split(pat, line)
        if len(parts) >= 2:
            return [p.strip() for p in parts]
    # Single-space split as last resort (only if enough words for a table)
    parts = line.split()
    if len(parts) >= 3:
        return parts
    return [line]


def _parse_response_fields(text: str) -> list[dict]:
    """Parse response field table. Encoding-agnostic — uses type-word detection.

    Scans for the first block of consecutive lines where column 2 is a known
    type (Number, String, Array, Object, etc.). Uses indentation for nesting.
    """
    # First try: look for a table within a "response" section (English keyword)
    scope = text
    resp_marker = re.search(r'(?im)^(?:#{1,3}\s*)?(?:response|return|响应|返回)', text)
    if resp_marker:
        scope = text[resp_marker.start():]

    start = _find_table_start(scope)
    if start is None:
        # Fallback: scan entire text for type-pattern table
        start = _find_table_start(text)

    if start is None:
        return []

    # Adjust start if we used a response marker scope
    if resp_marker:
        start = resp_marker.start() + start

    table_text = text[start:]
    lines = table_text.split("\n")
    stack: list[dict] = []
    fields: list[dict] = []

    # Skip header line (first line of table)
    line_idx = 1
    for line in lines[1:]:
        line_idx += 1
        stripped = line.strip()

        # Stop conditions
        if not stripped:
            if fields:
                break
            continue
        if re.match(r'^[-=|]{3,}$', stripped):
            if fields:
                break
            continue
        if re.match(r'^(https?://|\{|\}|GET|POST|PUT|PATCH|DELETE)\s', stripped):
            break

        indent = len(line) - len(line.lstrip())

        # Split into columns
        if '|' in stripped:
            parts = [p.strip() for p in stripped.split('|') if p.strip()]
        elif '\t' in stripped:
            parts = [p.strip() for p in stripped.split('\t') if p.strip()]
        else:
            parts = re.split(r'\s{2,}', stripped)
            if len(parts) < 2:
                # Single-space fallback
                m = re.match(r'(\S+)\s+(\S+)\s+(.*)', stripped)
                if m:
                    parts = [m.group(1), m.group(2), m.group(3)]

        if len(parts) < 2:
            continue

        name = parts[0].strip()
        field_type = "String"
        description = ""
        col = 1

        if _is_type(parts[1]):
            field_type = parts[1].strip()
            col = 2
        if len(parts) > col:
            description = parts[col].strip()

        # Build path from indent stack
        while stack and stack[-1].get("_indent", 0) >= indent:
            stack.pop()

        parent_path = ""
        for item in stack:
            p = item["_clean_name"]
            if item["_type"] == "Array":
                parent_path += f"{p}[]."
            else:
                parent_path += f"{p}."

        path = parent_path + name

        field = {
            "path": path,
            "type": field_type,
            "description": description,
            "_indent": indent,
            "_clean_name": name,
            "_type": field_type,
        }
        fields.append(field)

        if field_type in ("Object", "Array"):
            stack.append(field)

    return [
        {"path": f["path"], "type": f["type"], "description": f["description"]}
        for f in fields
    ]


def _is_type(text: str) -> bool:
    t = text.strip().lower()
    return t in {"string", "number", "integer", "boolean", "array", "object",
                 "float", "double", "int", "str", "bool", "date", "datetime"}


def _build_request_url(endpoint: str, params: list[dict]) -> tuple[str, list[str]]:
    """Build the final request URL from the endpoint and parsed parameters.

    Only includes required params and values from the endpoint URL itself.
    Optional params with auto-extracted default values (like page=1) are excluded
    to avoid accidentally enabling pagination/limits.
    """
    base = endpoint.split("?")[0]
    existing_query = {}
    if "?" in endpoint:
        for pair in endpoint.split("?")[1].split("&"):
            if "=" in pair:
                k, v = pair.split("=", 1)
                existing_query[k] = v

    query_params = dict(existing_query)
    missing = []
    # Pagination params that should NOT be auto-included (they'd limit results)
    PAGINATION_PARAMS = {"page", "per_page", "limit", "offset", "cursor", "size"}

    for p in params:
        name = p["name"]
        if p.get("required"):
            val = p.get("value") or existing_query.get(name)
            if not val:
                missing.append(name)
            elif val:
                query_params[name] = val
        elif name in existing_query:
            # Keep values already present in the endpoint URL
            query_params[name] = existing_query[name]
        elif name.lower() in PAGINATION_PARAMS:
            # Skip pagination params so we get all results, not just page 1
            continue
        elif p.get("value") and name.lower() not in PAGINATION_PARAMS:
            # Include non-pagination optional params with values
            query_params[name] = p["value"]

    if not query_params:
        return base, missing

    qs = "&".join(f"{k}={v}" for k, v in query_params.items())
    return f"{base}?{qs}", missing


# ── 第 3 步：接口请求 ──────────────────────────────────────

def fetch_api(request_url: str, timeout: int = 30) -> dict:
    """执行 GET 请求，返回响应数据。"""
    req = Request(request_url, headers={"Accept": "application/json", "User-Agent": USER_AGENT}, method="GET")
    try:
        with urlopen(req, timeout=timeout) as resp:
            body = resp.read()
            return {
                "ok": 200 <= resp.getcode() < 300,
                "status_code": resp.getcode(),
                "content_type": resp.headers.get("Content-Type", ""),
                "body": body,
                "json": _parse_json(body),
                "byte_count": len(body),
            }
    except HTTPError as e:
        body = e.read()
        return {
            "ok": False,
            "status_code": e.code,
            "content_type": e.headers.get("Content-Type", ""),
            "body": body,
            "json": _parse_json(body),
            "byte_count": len(body),
            "error": f"HTTP {e.code} {e.reason}",
        }
    except (URLError, TimeoutError) as e:
        return {"ok": False, "error": str(e)}


def _parse_json(body: bytes) -> Any | None:
    try:
        return json.loads(body.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None


# ── 第 4 步：数据整理 ──────────────────────────────────────

def normalize_data(json_data: Any, response_fields: list[dict]) -> dict:
    """定位主数据数组，按字段路径展平为结构化记录。"""
    main_array, array_path = _find_main_array(json_data)
    if main_array is None:
        # 如果是对象则作为单条
        main_array = [json_data] if isinstance(json_data, dict) else []
        array_path = "$"

    records = []
    for item in main_array:
        record = {}
        if response_fields:
            for f in response_fields:
                record[f["path"]] = _extract_field(item, f["path"])
        else:
            # 没有字段表时，自动展平顶层 key
            if isinstance(item, dict):
                for k, v in item.items():
                    if not isinstance(v, (dict, list)):
                        record[k] = _format_value(v)
                    elif isinstance(v, list):
                        record[k] = "; ".join(_format_value(x) for x in v[:10])
        records.append(record)

    return {
        "records": records,
        "items_count": len(records),
        "main_array_path": array_path,
        "fields_used": list(records[0].keys()) if records else [],
    }


def _find_main_array(data: Any) -> tuple[list | None, str]:
    """Locate the primary data array in a JSON response.

    Collects all array candidates (keyed by MAIN_ARRAY_KEYS or found recursively),
    returns the largest one. This prevents picking a small nested array (e.g., 9
    line-items) over the main results array (e.g., 41 orders).
    """
    candidates: list[tuple[list, str]] = []

    def _collect(obj: Any, prefix: str) -> None:
        if isinstance(obj, list):
            candidates.append((obj, prefix))
            return
        if isinstance(obj, dict):
            for key in MAIN_ARRAY_KEYS:
                val = obj.get(key)
                if isinstance(val, list):
                    candidates.append((val, f"{prefix}{key}"))
            for key, val in obj.items():
                if isinstance(val, (dict, list)):
                    _collect(val, f"{prefix}{key}.")

    _collect(data, "")

    if not candidates:
        return None, "$"

    # Return the largest array (most likely the main data)
    largest = max(candidates, key=lambda c: len(c[0]))
    return largest[0], largest[1].rstrip(".")


def _extract_field(obj: Any, path: str) -> str:
    """按点号路径从对象中提取字段值。"""
    # 处理数组路径如 reward.items[].name
    parts = re.split(r'\.', path)
    current = obj
    for part in parts:
        if current is None:
            return ""
        if "[]" in part:
            # 数组字段
            arr_key = part.replace("[]", "")
            if isinstance(current, dict):
                arr = current.get(arr_key)
            else:
                arr = current
            if isinstance(arr, list):
                rest = part.split("[]", 1)[1].lstrip(".")
                if rest:
                    values = [_extract_field(item, rest) for item in arr]
                    return "; ".join(str(v) for v in values if v)
                return "; ".join(str(x) for x in arr)
            return ""
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return ""
    return _format_value(current)


def _format_value(val: Any) -> str:
    if val is None:
        return ""
    if isinstance(val, bool):
        return str(val)
    if isinstance(val, (int, float)):
        return str(val)
    if isinstance(val, (dict, list)):
        return json.dumps(val, ensure_ascii=False)
    return str(val)


# ── 第 5 步：导出 ──────────────────────────────────────────

def export_data(records: list[dict], fields: list[str], format_name: str, output_dir: Path) -> Path:
    """导出数据到文件。返回文件路径。"""
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    output_dir.mkdir(parents=True, exist_ok=True)

    if format_name == "csv":
        path = output_dir / f"api-data-{timestamp}.csv"
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerows(records)

    elif format_name == "json":
        path = output_dir / f"api-data-{timestamp}.json"
        path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")

    else:  # markdown
        path = output_dir / f"api-data-{timestamp}.md"
        lines = []
        if fields:
            lines.append("| " + " | ".join(fields) + " |")
            lines.append("| " + " | ".join("---" for _ in fields) + " |")
        for row in records:
            lines.append("| " + " | ".join(str(row.get(f, "")) for f in fields) + " |")
        path.write_text("\n".join(lines), encoding="utf-8")

    return path


# ── 工具函数 ──────────────────────────────────────────────

def mask_sensitive(obj: Any) -> Any:
    """脱敏敏感字段（token/key/secret/password）。"""
    if isinstance(obj, dict):
        return {
            k: "***" if _is_sensitive(k) and v else mask_sensitive(v)
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [mask_sensitive(item) for item in obj]
    return obj


def _is_sensitive(key: str) -> bool:
    lowered = key.lower()
    return lowered in SENSITIVE_KEYS or lowered.endswith(
        ("_token", "_api_key", "_secret", "_password")
    )


def preview_text(text: str, length: int = 200) -> str:
    return text[:length].replace("\n", "\\n")


# ── 入口 ───────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="从 API 文档中提取 GET 接口数据")
    parser.add_argument("--doc", required=True, help="API 文档路径 (PDF/MD/TXT)")
    parser.add_argument("--format", default="markdown", choices=("markdown", "csv", "json"))
    parser.add_argument("--output", help="可选导出路径")
    parser.add_argument("--timeout", type=int, default=30, help="HTTP 超时秒数")
    parser.add_argument("--dry-run", action="store_true", help="仅解析，不请求接口")
    parser.add_argument("--param", action="append", default=[],
                        metavar="KEY=VALUE", help="传递参数值（可多次使用，如 --param api_token=xxx --param project_id=100001）")
    args = parser.parse_args()

    # 解析 --param 传入的键值对
    user_params: dict[str, str] = {}
    for pv in args.param:
        if "=" in pv:
            k, v = pv.split("=", 1)
            user_params[k.strip()] = v.strip()

    doc_path = Path(args.doc)
    if not doc_path.exists():
        print(json.dumps({"ok": False, "error": f"文档不存在：{args.doc}"}, ensure_ascii=False))
        sys.exit(1)

    # 确定输出目录
    root = Path(__file__).resolve().parents[3]
    output_root = root / "workspace" / "api-extractor"
    raw_dir = output_root / "raw"
    export_dir = output_root / "exports"

    # 阶段 1：提取文本
    text = extract_text(doc_path)
    if not text.strip():
        print(json.dumps({"ok": False, "error": "文档无可提取文本"}, ensure_ascii=False))
        sys.exit(1)

    # 阶段 2：解析
    parsed = parse_api_doc(text)
    selected = parsed.get("selected")
    if not selected:
        print(json.dumps({"ok": False, "error": parsed.get("error", "未找到 GET 接口"), "interfaces": parsed.get("interfaces", [])}, ensure_ascii=False))
        sys.exit(1)

    # 注入用户提供的参数值
    if user_params:
        for p in selected["params"]:
            if p["name"] in user_params:
                p["value"] = user_params[p["name"]]
        # 重新拼接 URL
        selected["request_url"], selected["missing_required_params"] = _build_request_url(
            selected["endpoint_url"], selected["params"],
        )

    # 脱敏输出
    safe_plan = mask_sensitive({
        "ok": True,
        "method": selected["method"],
        "endpoint_url": selected["endpoint_url"],
        "request_url": selected["request_url"],
        "params": selected["params"],
        "missing_required_params": selected["missing_required_params"],
        "response_fields_count": len(selected["response_fields"]),
        "text_preview": preview_text(text),
    })

    if args.dry_run:
        print(json.dumps(safe_plan, ensure_ascii=False, indent=2))
        return

    # 阶段 3：GET 检查
    if selected["method"] != "GET":
        print(json.dumps({
            "ok": False,
            "error": f"接口方法为 {selected['method']}，仅自动执行 GET 请求。请手动确认后重试。",
        }, ensure_ascii=False))
        sys.exit(1)

    if selected["missing_required_params"]:
        print(json.dumps({
            "ok": False,
            "error": f"缺少必填参数：{', '.join(selected['missing_required_params'])}",
        }, ensure_ascii=False))
        sys.exit(1)

    # 阶段 4：请求
    fetch_result = fetch_api(selected["request_url"], timeout=args.timeout)
    if not fetch_result["ok"]:
        print(json.dumps({"ok": False, "error": fetch_result.get("error", "请求失败"), "status_code": fetch_result.get("status_code")}, ensure_ascii=False))
        sys.exit(1)

    # 保存原始响应
    raw_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    raw_path = raw_dir / f"api-response-{ts}.json"
    raw_path.write_bytes(fetch_result["body"])

    # 阶段 5：整理
    if fetch_result["json"] is None:
        print(json.dumps({"ok": False, "error": "响应不是有效 JSON"}, ensure_ascii=False))
        sys.exit(1)

    normalized = normalize_data(fetch_result["json"], selected["response_fields"])

    # 阶段 6：导出
    output_path = Path(args.output) if args.output else None
    if not output_path:
        output_path = export_data(
            normalized["records"],
            normalized["fields_used"],
            args.format,
            export_dir,
        )

    summary = {
        "ok": True,
        "method": selected["method"],
        "endpoint_url": selected["endpoint_url"],
        "request_url": mask_sensitive(selected["request_url"]),
        "items_count": normalized["items_count"],
        "fields": normalized["fields_used"],
        "export_path": str(output_path),
        "raw_response_path": str(raw_path),
        "format": args.format,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
