from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


METHOD_RE = re.compile(r"\b(GET|POST|PUT|PATCH|DELETE)\b\s+(https?://\S+)", re.IGNORECASE)
PARAM_RE = re.compile(
    r"^(?P<indent>\s*)(?P<name>[A-Za-z_][\w-]*)\s+"
    r"(?:(?P<type>String|Number|Array|Object|Boolean|Integer)\s+)?"
    r"(?P<required>必填|选填)\s*(?P<tail>.*)$",
    re.IGNORECASE,
)
RESPONSE_FIELD_RE = re.compile(
    r"^(?P<indent>\s*)(?P<name>[A-Za-z_][\w-]*)\s+"
    r"(?P<type>String|Number|Array|Object|Boolean|Integer)\s*(?P<tail>.*)$",
    re.IGNORECASE,
)
DEFAULT_RE = re.compile(r"(?:默认|default)\s*(?:[A-Za-z_][\w-]*\s*)?=?\s*([^\s，,。；;]+)", re.IGNORECASE)
ENUM_RE = re.compile(r"可选参数[:：]\s*([A-Za-z0-9_./|-]+)")

TYPE_NAMES = {"String", "Number", "Array", "Object", "Boolean", "Integer"}
READ_ONLY_METHODS = {"GET"}
REQUEST_STOP_MARKERS = ("响应参数", "返回参数", "请求示例", "响应示例", "返回示例")
RESPONSE_SECTION_MARKERS = ("响应参数", "返回参数", "Response Parameters", "Response Fields")
RESPONSE_STOP_MARKERS = (
    "请求示例",
    "响应示例",
    "返回示例",
    "Request Example",
    "Response Example",
    "上传 Tracking Code",
    "上传Tracking Code",
    "创建订单",
)
PLACEHOLDER_MARKERS = ("联系我们获取", "联系我", "your_", "xxx", "待填写", "todo")
SENSITIVE_NAMES = ("api_token", "token", "api_key", "key", "secret", "password")


@dataclass
class Parameter:
    path: str
    required: bool
    type: str | None = None
    description: str = ""
    value: str | None = None
    value_source: str | None = None
    default_value: str | None = None
    enum_values: list[str] = field(default_factory=list)
    indent: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "type": self.type,
            "required": self.required,
            "description": self.description,
            "value": self.value,
            "value_source": self.value_source,
            "default_value": self.default_value,
            "enum_values": self.enum_values,
        }


@dataclass
class ResponseField:
    path: str
    type: str | None = None
    description: str = ""
    indent: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "type": self.type,
            "description": self.description,
        }


@dataclass
class InterfaceBlock:
    title: str | None
    method: str
    endpoint_url: str
    params: list[Parameter]
    response_fields: list[ResponseField]

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "method": self.method,
            "endpoint_url": self.endpoint_url,
            "params": [param.to_dict() for param in self.params],
            "response_fields": [field.to_dict() for field in self.response_fields],
        }


def parse_api_document(text: str, candidate_urls: list[str] | None = None) -> dict[str, Any]:
    lines = normalize_lines(text)
    blocks = parse_interface_blocks(lines)
    candidate_urls = unique_urls(extract_urls(text) + (candidate_urls or []))
    selected = select_read_only_block(blocks)
    if not selected:
        return {
            "interfaces_count": len(blocks),
            "selected_index": None,
            "request_plan": empty_request_plan(),
            "warnings": ["no_get_endpoint_found"] if blocks else ["no_endpoint_found"],
        }

    selected_index = blocks.index(selected)
    request_plan = build_request_plan(selected, candidate_urls)
    warnings: list[str] = []
    if not request_plan.get("response_fields"):
        warnings.append("no_response_fields_found")
    return {
        "interfaces_count": len(blocks),
        "selected_index": selected_index,
        "selected_title": selected.title,
        "candidate_urls_count": len(candidate_urls),
        "interfaces": [block.to_dict() for block in blocks],
        "request_plan": request_plan,
        "warnings": warnings,
    }


def normalize_lines(text: str) -> list[str]:
    text = text.replace("\f", "\n")
    return [line.rstrip() for line in text.splitlines()]


def parse_interface_blocks(lines: list[str]) -> list[InterfaceBlock]:
    method_indexes: list[tuple[int, re.Match[str]]] = []
    for index, line in enumerate(lines):
        match = METHOD_RE.search(line)
        if match:
            method_indexes.append((index, match))

    blocks: list[InterfaceBlock] = []
    for position, (start, match) in enumerate(method_indexes):
        end = method_indexes[position + 1][0] if position + 1 < len(method_indexes) else len(lines)
        block_lines = lines[start:end]
        title = find_title(lines, start)
        method = match.group(1).upper()
        endpoint_url = clean_url(match.group(2))
        params = parse_request_params(block_lines[1:])
        response_fields = parse_response_fields(block_lines[1:])
        blocks.append(
            InterfaceBlock(
                title=title,
                method=method,
                endpoint_url=endpoint_url,
                params=params,
                response_fields=response_fields,
            )
        )
    return blocks


def find_title(lines: list[str], method_index: int) -> str | None:
    for index in range(method_index - 1, max(method_index - 8, -1), -1):
        candidate = lines[index].strip()
        if candidate:
            return candidate
    return None


def parse_request_params(lines: list[str]) -> list[Parameter]:
    params: list[Parameter] = []
    stack: list[Parameter] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if any(marker in stripped for marker in REQUEST_STOP_MARKERS):
            break

        row_match = parse_request_table_row(line)
        if row_match:
            indent = row_match["indent"]
            name = row_match["name"]
            param_type = normalize_type(row_match["type"])
            required = row_match["required"] == "必填"
            tail = clean_tail(row_match["tail"])
            value, description, default_value, enum_values = classify_tail(name, tail)

            while stack and stack[-1].indent >= indent:
                stack.pop()
            path = build_param_path(stack, name)
            param = Parameter(
                path=path,
                type=param_type,
                required=required,
                description=description,
                value=value,
                value_source="request_table" if value is not None else None,
                default_value=default_value,
                enum_values=enum_values,
                indent=indent,
            )
            params.append(param)
            if param_type in {"Object", "Array"}:
                stack.append(param)
            continue

        match = PARAM_RE.match(line)
        if not match:
            attach_continuation(params, stripped)
            continue

        indent = len(match.group("indent").replace("\t", "    "))
        name = match.group("name")
        param_type = normalize_type(match.group("type"))
        required = match.group("required") == "必填"
        tail = clean_tail(match.group("tail"))
        value, description, default_value, enum_values = classify_tail(name, tail)

        while stack and stack[-1].indent >= indent:
            stack.pop()
        path = build_param_path(stack, name)
        param = Parameter(
            path=path,
            type=param_type,
            required=required,
            description=description,
            value=value,
            value_source="request_table" if value is not None else None,
            default_value=default_value,
            enum_values=enum_values,
            indent=indent,
        )
        params.append(param)
        if param_type in {"Object", "Array"}:
            stack.append(param)
    return params


def parse_response_fields(lines: list[str]) -> list[ResponseField]:
    start_index = find_response_section_start(lines)
    if start_index is None:
        return []

    fields: list[ResponseField] = []
    stack: list[ResponseField] = []
    for line in lines[start_index + 1 :]:
        stripped = line.strip()
        if not stripped:
            continue
        if any(marker in stripped for marker in RESPONSE_STOP_MARKERS):
            break

        parsed = parse_response_field_row(line)
        if parsed is None:
            attach_response_continuation(fields, stripped)
            continue

        indent = parsed["indent"]
        name = parsed["name"]
        field_type = normalize_type(parsed["type"])
        description = clean_tail(parsed["tail"])

        while stack and stack[-1].indent >= indent:
            stack.pop()
        path = build_field_path(stack, name)
        field = ResponseField(
            path=path,
            type=field_type,
            description=description,
            indent=indent,
        )
        fields.append(field)
        if field_type in {"Object", "Array"}:
            stack.append(field)

    return fields


def parse_request_table_row(line: str) -> dict[str, Any] | None:
    required_match = re.search(r"(必填|选填)", line)
    if not required_match:
        return None

    name_part = line[: required_match.start()]
    tail_part = line[required_match.end() :]
    if not name_part.strip():
        return None

    name_tokens = name_part.split()
    if not name_tokens:
        return None

    name = name_tokens[0]
    if not re.fullmatch(r"[A-Za-z_][\w-]*", name):
        return None

    param_type = None
    if len(name_tokens) > 1:
        type_candidate = name_tokens[-1]
        if normalize_type(type_candidate) in TYPE_NAMES:
            param_type = normalize_type(type_candidate)

    indent = len(name_part) - len(name_part.lstrip(" "))
    tail = tail_part.rstrip()
    return {
        "indent": indent,
        "name": name,
        "type": param_type,
        "required": required_match.group(1),
        "tail": tail,
    }


def parse_response_field_row(line: str) -> dict[str, Any] | None:
    match = RESPONSE_FIELD_RE.match(line)
    if match:
        return {
            "indent": len(match.group("indent").replace("\t", "    ")),
            "name": match.group("name"),
            "type": match.group("type"),
            "tail": match.group("tail"),
        }

    stripped = line.strip()
    if not stripped:
        return None

    parts = stripped.split()
    if len(parts) < 2:
        return None
    name = parts[0]
    if not re.fullmatch(r"[A-Za-z_][\w-]*", name):
        return None

    type_index = None
    for index, token in enumerate(parts[1:], start=1):
        normalized = normalize_type(token)
        if normalized in TYPE_NAMES:
            type_index = index
            break
    if type_index is None:
        return None

    indent = len(line) - len(line.lstrip(" \t"))
    tail = " ".join(parts[type_index + 1 :])
    return {
        "indent": indent,
        "name": name,
        "type": parts[type_index],
        "tail": tail,
    }


def attach_continuation(params: list[Parameter], stripped: str) -> None:
    if not params:
        return
    default_value = extract_default(stripped)
    enum_values = extract_enums(stripped)
    if default_value and not params[-1].default_value:
        params[-1].default_value = default_value
    if enum_values and not params[-1].enum_values:
        params[-1].enum_values = enum_values
    if stripped and not looks_like_url(stripped):
        params[-1].description = " ".join(part for part in (params[-1].description, stripped) if part)


def attach_response_continuation(fields: list[ResponseField], stripped: str) -> None:
    if not fields:
        return
    if is_section_header(stripped) or looks_like_url(stripped):
        return
    fields[-1].description = " ".join(part for part in (fields[-1].description, stripped) if part)


def build_param_path(stack: list[Parameter], name: str) -> str:
    if not stack:
        return name
    parent = stack[-1]
    if parent.type == "Array":
        return f"{parent.path}[].{name}"
    return f"{parent.path}.{name}"


def build_field_path(stack: list[ResponseField], name: str) -> str:
    if not stack:
        return name
    parent = stack[-1]
    if parent.type == "Array":
        return f"{parent.path}[].{name}"
    return f"{parent.path}.{name}"


def find_response_section_start(lines: list[str]) -> int | None:
    for index, line in enumerate(lines):
        if any(marker in line for marker in RESPONSE_SECTION_MARKERS):
            return index
    return None


def classify_tail(name: str, tail: str) -> tuple[str | None, str, str | None, list[str]]:
    if not tail:
        return None, "", None, []

    default_value = extract_default(tail)
    enum_values = extract_enums(tail)
    if is_placeholder(tail):
        return None, tail, default_value, enum_values

    value, description = split_value_and_description(name, tail)
    if value is not None:
        return value, description, default_value, enum_values
    return None, tail, default_value, enum_values


def split_value_and_description(name: str, tail: str) -> tuple[str | None, str]:
    compact = tail.strip()
    if not compact:
        return None, ""

    if is_sensitive_name(name):
        tokens = compact.split()
        value_tokens: list[str] = []
        for token in tokens:
            if is_scalar_value(name, token):
                value_tokens.append(token)
            else:
                break
        if value_tokens:
            raw_value = "".join(value_tokens)
            remainder = compact
            for token in value_tokens:
                remainder = remainder.replace(token, "", 1).strip()
            return normalize_scalar_value(name, raw_value), remainder
        return None, compact

    parts = compact.split()
    if not parts:
        return None, ""
    first = parts[0]
    if is_scalar_value(name, first):
        remainder = compact[len(first) :].strip()
        return normalize_scalar_value(name, first), remainder
    return None, compact


def extract_default(text: str) -> str | None:
    match = DEFAULT_RE.search(text)
    return match.group(1) if match else None


def extract_enums(text: str) -> list[str]:
    match = ENUM_RE.search(text)
    if not match:
        return []
    return [item for item in re.split(r"[/|]", match.group(1)) if item]


def is_placeholder(value: str) -> bool:
    lowered = value.lower()
    return any(marker.lower() in lowered for marker in PLACEHOLDER_MARKERS)


def is_scalar_value(name: str, tail: str) -> bool:
    if is_sensitive_name(name):
        return not contains_cjk(tail)
    if contains_cjk(tail):
        return False
    return bool(re.fullmatch(r"[A-Za-z0-9_.@:/?&=%+-]+", tail.replace(" ", "")))


def normalize_scalar_value(name: str, value: str) -> str:
    if is_sensitive_name(name):
        return re.sub(r"\s+", "", value)
    return value.strip()


def is_sensitive_name(name: str) -> bool:
    lowered = name.lower()
    return any(marker in lowered for marker in SENSITIVE_NAMES)


def contains_cjk(text: str) -> bool:
    return bool(re.search(r"[\u3400-\u9fff]", text))


def normalize_type(value: str | None) -> str | None:
    if not value:
        return None
    for known in TYPE_NAMES:
        if value.lower() == known.lower():
            return known
    return value


def clean_tail(value: str) -> str:
    return " ".join(value.strip().split())


def clean_url(url: str) -> str:
    return url.strip().rstrip("。；;,，")


def looks_like_url(value: str) -> bool:
    return value.startswith(("http://", "https://"))


def is_section_header(value: str) -> bool:
    return any(marker in value for marker in REQUEST_STOP_MARKERS + RESPONSE_STOP_MARKERS)


def select_read_only_block(blocks: list[InterfaceBlock]) -> InterfaceBlock | None:
    for block in blocks:
        if block.method in READ_ONLY_METHODS:
            return block
    return None


def build_request_plan(block: InterfaceBlock, candidate_urls: list[str] | None = None) -> dict[str, Any]:
    endpoint_params = dict(parse_qsl(urlsplit(block.endpoint_url).query, keep_blank_values=True))
    query: dict[str, str] = dict(endpoint_params)
    fallback_query = find_matching_url_query(block.endpoint_url, candidate_urls or [])
    missing_required: list[str] = []
    query_param_paths: list[str] = []
    filled_required_params: list[str] = []
    filled_optional_params: list[str] = []
    skipped_optional_params: list[str] = []
    fallback_filled_params: list[str] = []

    for param in block.params:
        if "." in param.path or "[]" in param.path:
            continue
        fallback_value = fallback_query.get(param.path)
        if fallback_value is not None and (param.value is None or is_sensitive_name(param.path)):
            param.value = fallback_value
            param.value_source = "document_url_fallback"
            fallback_filled_params.append(param.path)

        if param.value is not None:
            query[param.path] = param.value
            query_param_paths.append(param.path)
            if param.required:
                filled_required_params.append(param.path)
            else:
                filled_optional_params.append(param.path)
        elif param.required and param.path not in query:
            missing_required.append(param.path)
        elif not param.required:
            skipped_optional_params.append(param.path)

    request_url = build_url(block.endpoint_url, query)
    return {
        "method": block.method,
        "title": block.title,
        "endpoint_url": strip_query(block.endpoint_url),
        "request_url": request_url if not missing_required else None,
        "query": query,
        "query_param_paths": query_param_paths,
        "filled_required_params": filled_required_params,
        "filled_optional_params": filled_optional_params,
        "fallback_filled_params": fallback_filled_params,
        "skipped_optional_params": skipped_optional_params,
        "missing_required_params": missing_required,
        "risk_level": "read_only" if block.method == "GET" else "side_effect",
        "params": [param.to_dict() for param in block.params],
        "response_fields": [field.to_dict() for field in block.response_fields],
    }


def build_url(endpoint_url: str, query: dict[str, str]) -> str:
    split = urlsplit(endpoint_url)
    query_text = urlencode(query, doseq=True)
    return urlunsplit((split.scheme, split.netloc, split.path, query_text, split.fragment))


def strip_query(url: str) -> str:
    split = urlsplit(url)
    return urlunsplit((split.scheme, split.netloc, split.path, "", split.fragment))


def find_matching_url_query(endpoint_url: str, candidate_urls: list[str]) -> dict[str, str]:
    endpoint = strip_query(endpoint_url)
    for url in candidate_urls:
        if strip_query(url) == endpoint:
            query = dict(parse_qsl(urlsplit(url).query, keep_blank_values=True))
            if query:
                return query
    return {}


def extract_urls(text: str) -> list[str]:
    matches = re.findall(r"https?://[^\s\"'<>]+", text)
    return unique_urls(clean_url(match) for match in matches)


def unique_urls(urls: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for url in urls:
        if url and url not in seen:
            seen.add(url)
            result.append(url)
    return result


def empty_request_plan() -> dict[str, Any]:
    return {
        "method": None,
        "endpoint_url": None,
        "request_url": None,
        "query": {},
        "query_param_paths": [],
        "filled_required_params": [],
        "filled_optional_params": [],
        "fallback_filled_params": [],
        "skipped_optional_params": [],
        "missing_required_params": [],
        "risk_level": "unknown",
        "params": [],
        "response_fields": [],
    }
