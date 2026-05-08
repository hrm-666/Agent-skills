from __future__ import annotations

from pathlib import Path

MAX_CHARS = 10000


def create_file_handlers(project_root: Path):
    allowed_write_roots = [
        (project_root / "workspace").resolve(),
        (project_root / "uploads").resolve(),
        (project_root / "logs").resolve(),
    ]

    def resolve_path(raw_path: str) -> Path:
        candidate = Path(raw_path).expanduser()
        if not candidate.is_absolute():
            candidate = (project_root / candidate).resolve()
        else:
            candidate = candidate.resolve()
        return candidate

    def read(path: str) -> str:
        target = resolve_path(path)
        if not target.exists() or not target.is_file():
            return f"[error] File not found: {path}"

        head = target.read_bytes()[:4096]
        if b"\x00" in head:
            return "[error] Binary file is not supported by read tool"

        try:
            content = target.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return "[error] Binary or non-UTF8 file is not supported by read tool"

        if len(content) > MAX_CHARS:
            return f"{content[:MAX_CHARS]}\n...[truncated, total={len(content)} chars]"
        return content

    def write(path: str, content: str) -> str:
        target = resolve_path(path)
        if not any(target.is_relative_to(root) for root in allowed_write_roots):
            return "[error] write only allowed under workspace/, uploads/, logs/"

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"Wrote {len(content)} chars to {target}"

    return read, write
