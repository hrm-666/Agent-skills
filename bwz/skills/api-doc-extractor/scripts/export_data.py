from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class ExportResult:
    ok: bool
    format: str
    path: str
    record_count: int
    warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "format": self.format,
            "path": self.path,
            "record_count": self.record_count,
            "warnings": self.warnings,
        }


def export_normalized_data(
    *,
    records: list[dict[str, str]],
    fields_used: list[str],
    format_name: str,
    output_root: Path,
    output_path: str | None = None,
) -> ExportResult:
    export_path = resolve_export_path(
        output_root=output_root,
        format_name=format_name,
        output_path=output_path,
    )
    export_path.parent.mkdir(parents=True, exist_ok=True)

    if format_name == "json":
        write_json(export_path, records=records, fields_used=fields_used)
    elif format_name == "csv":
        write_csv(export_path, records=records, fields_used=fields_used)
    elif format_name == "markdown":
        write_markdown(export_path, records=records, fields_used=fields_used)
    else:
        raise ValueError(f"unsupported_export_format:{format_name}")

    return ExportResult(
        ok=True,
        format=format_name,
        path=str(export_path),
        record_count=len(records),
        warnings=[],
    )


def save_plan_summary(plan: dict[str, Any], *, output_root: Path) -> Path:
    plans_dir = output_root / "plans"
    plans_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    plan_path = plans_dir / f"run-summary-{timestamp}.json"
    plan_path.write_text(
        json.dumps(plan, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return plan_path


def resolve_export_path(*, output_root: Path, format_name: str, output_path: str | None) -> Path:
    if output_path:
        return Path(output_path).resolve()

    exports_dir = output_root / "exports"
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    suffix_map = {
        "markdown": ".md",
        "csv": ".csv",
        "json": ".json",
    }
    return exports_dir / f"normalized-data-{timestamp}{suffix_map[format_name]}"


def write_json(path: Path, *, records: list[dict[str, str]], fields_used: list[str]) -> None:
    payload = {
        "record_count": len(records),
        "fields_used": fields_used,
        "records": records,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_csv(path: Path, *, records: list[dict[str, str]], fields_used: list[str]) -> None:
    fieldnames = collect_fieldnames(records, fields_used)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            writer.writerow({name: record.get(name, "") for name in fieldnames})


def write_markdown(path: Path, *, records: list[dict[str, str]], fields_used: list[str]) -> None:
    fieldnames = collect_fieldnames(records, fields_used)
    lines = [
        "# API Extracted Data",
        "",
        f"- record_count: {len(records)}",
        f"- field_count: {len(fieldnames)}",
        "",
    ]
    if not fieldnames:
        lines.append("No fields were available for export.")
    else:
        lines.append("| " + " | ".join(escape_markdown(name) for name in fieldnames) + " |")
        lines.append("| " + " | ".join("---" for _ in fieldnames) + " |")
        for record in records:
            row = [escape_markdown(record.get(name, "")) for name in fieldnames]
            lines.append("| " + " | ".join(row) + " |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def collect_fieldnames(records: list[dict[str, str]], preferred: list[str]) -> list[str]:
    if preferred:
        return preferred
    names: list[str] = []
    seen: set[str] = set()
    for record in records:
        for key in record.keys():
            if key not in seen:
                seen.add(key)
                names.append(key)
    return names


def escape_markdown(value: object) -> str:
    text = str(value)
    text = text.replace("\r\n", " ").replace("\n", " ")
    return text.replace("|", "\\|")
