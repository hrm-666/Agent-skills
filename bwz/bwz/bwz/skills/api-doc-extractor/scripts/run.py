from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from extract_doc import extract_document, preview_text
from export_data import export_normalized_data, save_plan_summary
from fetch_api import fetch_from_plan
from normalize_data import normalize_from_raw_response
from parse_api_doc import empty_request_plan, parse_api_document


SUPPORTED_FORMATS = {"markdown", "csv", "json"}
SENSITIVE_KEYS = ("api_token", "token", "key", "secret", "password")


def project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def resolve_doc_path(raw_path: str) -> Path:
    doc_path = Path(raw_path)
    if doc_path.exists():
        return doc_path
    if not doc_path.is_absolute():
        root_candidate = project_root() / doc_path
        if root_candidate.exists():
            return root_candidate
    return doc_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Parse an API document and prepare a read-only extraction plan."
    )
    parser.add_argument("--doc", required=True, help="Path to the API document.")
    parser.add_argument(
        "--format",
        default="markdown",
        choices=sorted(SUPPORTED_FORMATS),
        help="Output format for normalized results.",
    )
    parser.add_argument("--output", help="Optional export path.")
    parser.add_argument("--max-pages", type=int, default=50, help="Maximum pages to fetch.")
    parser.add_argument("--timeout", type=int, default=30, help="HTTP timeout in seconds.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only build a request plan. Do not call the API.",
    )
    parser.add_argument(
        "--confirm-post",
        action="store_true",
        help="Allow side-effecting requests after explicit user confirmation.",
    )
    return parser.parse_args()


def is_sensitive_key_name(key: str) -> bool:
    lowered = key.lower()
    exact = {
        "api_token",
        "token",
        "access_token",
        "api_key",
        "secret",
        "password",
    }
    return lowered in exact or lowered.endswith(("_token", "_api_key", "_secret", "_password"))


def mask_sensitive(value: Any) -> Any:
    if isinstance(value, str):
        return redact_sensitive_text(value)
    if isinstance(value, dict):
        masked: dict[str, Any] = {}
        is_sensitive_record = any(
            any(marker in str(value.get(field, "")).lower() for marker in SENSITIVE_KEYS)
            for field in ("path", "name")
        )
        for key, item in value.items():
            if is_sensitive_key_name(key):
                masked[key] = "***" if item else item
            elif is_sensitive_record and key in {"value", "default_value"}:
                masked[key] = "***" if item else item
            else:
                masked[key] = mask_sensitive(item)
        return masked
    if isinstance(value, list):
        return [mask_sensitive(item) for item in value]
    return value


def redact_sensitive_text(text: str) -> str:
    text = re.sub(
        r"(?i)(api[_-]?token|api[_-]?key|access[_-]?token|secret|password|token|key)(=)[^&\s,\"]+",
        r"\1=***",
        text,
    )
    text = re.sub(
        r"(?im)^(\s*(?:api[_-]?token|api[_-]?key|access[_-]?token|secret|password|token|key)\s+)(?:必填|选填)?(\s+)(\S.*)$",
        r"\1***",
        text,
    )
    return text


def build_initial_plan(
    doc_path: Path,
    args: argparse.Namespace,
    extracted: dict[str, Any] | None = None,
    parsed: dict[str, Any] | None = None,
    fetch: dict[str, Any] | None = None,
    normalize: dict[str, Any] | None = None,
    export: dict[str, Any] | None = None,
) -> dict[str, Any]:
    exists = doc_path.exists()
    warnings = [] if exists else ["doc_not_found"]
    if extracted:
        warnings.extend(extracted.get("warnings", []))
    if parsed:
        warnings.extend(parsed.get("warnings", []))
    if fetch:
        warnings.extend(fetch.get("warnings", []))
    if normalize:
        warnings.extend(normalize.get("warnings", []))
    if export:
        warnings.extend(export.get("warnings", []))
    request_plan = parsed.get("request_plan") if parsed else empty_request_plan()
    stage = (
        "file_export"
        if export
        else "data_normalization"
        if normalize
        else "api_fetch"
        if fetch
        else "request_planning"
        if parsed
        else "document_extraction"
        if extracted
        else "skeleton"
    )
    return {
        "ok": exists,
        "stage": stage,
        "message": (
            "阶段六文件导出已运行：已将接口数据整理并写入目标文件。"
            if export
            else
            "阶段五字段整理已运行：已定位主数据数组，并按响应字段表扁平化为结构化记录。"
            if normalize
            else
            "阶段四接口请求已运行：已根据 request_url 执行 GET 请求并保存原始响应。"
            if fetch
            else
            "阶段三请求计划已运行：已提取文档文本，解析 GET endpoint，并尝试用参数表值拼接 request_url。"
            if parsed
            else
            "阶段二文档提取已运行：已接收参数并提取文档文本，后续阶段将接入参数表解析、请求执行和结果导出。"
            if extracted
            else "阶段一骨架已运行：已接收参数，后续阶段将接入文档提取、参数表解析、请求执行和结果导出。"
            if exists
            else "文档路径不存在。"
        ),
        "doc": {
            "path": str(doc_path),
            "exists": exists,
            "suffix": doc_path.suffix.lower(),
        },
        "extraction": extracted,
        "parse": {
            "interfaces_count": parsed.get("interfaces_count"),
            "selected_index": parsed.get("selected_index"),
            "selected_title": parsed.get("selected_title"),
        }
        if parsed
        else None,
        "request_plan": request_plan,
        "fetch": fetch,
        "normalize": normalize,
        "export": export,
        "options": {
            "format": args.format,
            "output": args.output,
            "max_pages": args.max_pages,
            "timeout": args.timeout,
            "dry_run": args.dry_run,
            "confirm_post": args.confirm_post,
        },
        "next_steps": [
            "extract_doc.py: extract text from PDF/Markdown/txt",
            "parse_api_doc.py: parse interface blocks and request parameter tables",
            "fetch_api.py: execute safe GET requests",
            "normalize_data.py: flatten JSON response fields",
            "export_data.py: export Markdown/CSV/JSON",
        ],
        "warnings": warnings,
    }


def print_json(payload: dict[str, Any]) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    buffer = getattr(sys.stdout, "buffer", None)
    if buffer is not None:
        buffer.write(text.encode("utf-8", errors="replace"))
        buffer.write(b"\n")
        return
    print(text)


def main() -> int:
    args = parse_args()
    doc_path = resolve_doc_path(args.doc)
    extracted_summary = None
    parsed_summary = None
    fetch_summary = None
    normalize_summary = None
    export_summary = None
    if doc_path.exists():
        extracted = extract_document(doc_path)
        extracted_summary = {
            "extractor": extracted.extractor,
            "char_count": extracted.char_count,
            "line_count": extracted.line_count,
            "candidate_urls_count": len(extracted.urls),
            "text_preview": preview_text(extracted.text),
            "warnings": extracted.warnings,
        }
        if extracted.text.strip():
            parsed_summary = parse_api_document(extracted.text, candidate_urls=extracted.urls)
            if parsed_summary and not args.dry_run:
                output_root = project_root() / "workspace" / "api-doc-extractor"
                fetch_summary = fetch_from_plan(
                    parsed_summary.get("request_plan", empty_request_plan()),
                    timeout=args.timeout,
                    output_root=output_root,
                ).to_dict()
                raw_paths = fetch_summary.get("raw_response_paths", []) if fetch_summary else []
                if fetch_summary.get("ok") and raw_paths:
                    normalized = normalize_from_raw_response(
                        raw_paths[0],
                        response_fields=parsed_summary.get("request_plan", {}).get("response_fields", []),
                    )
                    normalize_summary = normalized.to_dict()
                    export_summary = export_normalized_data(
                        records=normalized.records,
                        fields_used=normalized.fields_used,
                        format_name=args.format,
                        output_root=output_root,
                        output_path=args.output,
                    ).to_dict()
    plan = build_initial_plan(
        doc_path,
        args,
        extracted_summary,
        parsed_summary,
        fetch_summary,
        normalize_summary,
        export_summary,
    )
    masked_plan = mask_sensitive(plan)
    if doc_path.exists():
        output_root = project_root() / "workspace" / "api-doc-extractor"
        masked_plan["summary_path"] = str(save_plan_summary(masked_plan, output_root=output_root))
    print_json(masked_plan)
    return 0 if plan["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
