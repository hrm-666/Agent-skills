from __future__ import annotations

import subprocess
from dataclasses import dataclass
from html import unescape
from pathlib import Path
import re


SUPPORTED_TEXT_SUFFIXES = {".md", ".markdown", ".txt"}


@dataclass
class ExtractedDocument:
    source_path: str
    suffix: str
    text: str
    extractor: str
    warnings: list[str]
    urls: list[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.urls is None:
            self.urls = []

    @property
    def char_count(self) -> int:
        return len(self.text)

    @property
    def line_count(self) -> int:
        return len(self.text.splitlines())


@dataclass
class PdfTextExtraction:
    text: str
    extractor: str
    warnings: list[str]
    urls: list[str]


def extract_document(path: Path) -> ExtractedDocument:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return extract_pdf(path)
    if suffix in SUPPORTED_TEXT_SUFFIXES:
        return extract_text_file(path)
    return ExtractedDocument(
        source_path=str(path),
        suffix=suffix,
        text="",
        extractor="unsupported",
        warnings=[f"unsupported_document_type:{suffix or '<none>'}"],
        urls=[],
    )


def extract_text_file(path: Path) -> ExtractedDocument:
    warnings: list[str] = []
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            text = path.read_text(encoding=encoding)
            return ExtractedDocument(
                source_path=str(path),
                suffix=path.suffix.lower(),
                text=normalize_text(text),
                extractor=f"text:{encoding}",
                warnings=warnings,
                urls=extract_urls(text),
            )
        except UnicodeDecodeError:
            warnings.append(f"decode_failed:{encoding}")
    return ExtractedDocument(
        source_path=str(path),
        suffix=path.suffix.lower(),
        text="",
        extractor="text",
        warnings=warnings + ["text_decode_failed"],
        urls=[],
    )


def extract_pdf(path: Path) -> ExtractedDocument:
    warnings: list[str] = []
    for extractor in (
        extract_pdf_with_pymupdf,
        extract_pdf_with_pdftotext,
        extract_pdf_with_pypdf,
    ):
        result = extractor(path)
        warnings.extend(result.warnings)
        text = normalize_text(result.text)
        if text.strip():
            return ExtractedDocument(
                source_path=str(path),
                suffix=path.suffix.lower(),
                text=text,
                extractor=result.extractor,
                warnings=unique_strings(warnings),
                urls=unique_urls(extract_urls(text) + result.urls),
            )

    warnings.append("empty_extracted_text")
    return ExtractedDocument(
        source_path=str(path),
        suffix=path.suffix.lower(),
        text="",
        extractor="pdf",
        warnings=unique_strings(warnings),
        urls=[],
    )


def extract_pdf_with_pypdf(path: Path) -> PdfTextExtraction:
    try:
        from pypdf import PdfReader
    except ImportError:
        return PdfTextExtraction("", "pypdf", ["pypdf_not_installed"], [])

    try:
        reader = PdfReader(str(path))
        page_texts = [(page.extract_text() or "") for page in reader.pages]
    except Exception as exc:
        return PdfTextExtraction("", "pypdf", [f"pypdf_failed:{type(exc).__name__}"], [])

    text = normalize_text("\n".join(page_texts))
    warnings = [] if text.strip() else ["pypdf_empty_text"]
    return PdfTextExtraction(text, "pypdf", warnings, extract_urls(text))


def extract_pdf_with_pymupdf(path: Path) -> PdfTextExtraction:
    try:
        import fitz
    except ImportError:
        return PdfTextExtraction("", "pymupdf", ["pymupdf_not_installed"], [])

    try:
        doc = fitz.open(str(path))
    except Exception as exc:
        return PdfTextExtraction("", "pymupdf", [f"pymupdf_open_failed:{type(exc).__name__}"], [])

    try:
        text = normalize_text(extract_pymupdf_layout_text(doc))
        link_urls = []
        for page in doc:
            for link in page.get_links():
                uri = link.get("uri")
                if isinstance(uri, str) and uri.startswith(("http://", "https://")):
                    link_urls.append(clean_extracted_url(uri))
    except Exception as exc:
        return PdfTextExtraction("", "pymupdf", [f"pymupdf_extract_failed:{type(exc).__name__}"], [])
    finally:
        doc.close()

    warnings = [] if text.strip() else ["pymupdf_empty_text"]
    return PdfTextExtraction(text, "pymupdf", warnings, unique_urls(extract_urls(text) + link_urls))


def extract_pymupdf_layout_text(doc: object) -> str:
    page_rows: list[list[tuple[float, float, str]]] = []
    for page in doc:
        rows: list[tuple[float, float, str]] = []
        blocks = page.get_text("blocks", sort=True)
        for block in blocks:
            x0, y0, _x1, _y1, raw_text, *_rest = block
            text = collapse_pdf_block_text(raw_text)
            if text:
                rows.append((float(y0), float(x0), text))
        page_rows.append(rows)

    content_left = min(
        (x for rows in page_rows for _y, x, text in rows if text.strip()),
        default=0.0,
    )

    pages: list[str] = []
    for rows in page_rows:
        if not rows:
            pages.append("")
            continue

        page_lines = []
        for _y, x, text in rows:
            indent = infer_pdf_indent(x, content_left)
            page_lines.append(f"{' ' * indent}{text}")
        pages.append("\n".join(page_lines))
    return "\n\n".join(pages)


def collapse_pdf_block_text(raw_text: str) -> str:
    parts = [part.strip() for part in raw_text.splitlines()]
    parts = [part for part in parts if part]
    if not parts:
        return ""
    return " ".join(parts)


def infer_pdf_indent(x: float, content_left: float) -> int:
    offset = max(0.0, x - content_left)
    if offset < 6:
        return 0
    return int(round(offset / 10.0)) * 2


def extract_pdf_with_pdftotext(path: Path) -> PdfTextExtraction:
    command = ["pdftotext", "-layout", "-enc", "UTF-8", str(path), "-"]
    try:
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=30,
        )
    except FileNotFoundError:
        return PdfTextExtraction("", "pdftotext", ["pdftotext_not_found"], [])
    except subprocess.TimeoutExpired:
        return PdfTextExtraction("", "pdftotext", ["pdftotext_timeout"], [])

    warnings: list[str] = []
    if result.returncode != 0:
        warnings.append(f"pdftotext_exit:{result.returncode}")

    stderr = result.stderr.decode("utf-8", errors="replace").strip()
    if stderr:
        warnings.append("pdftotext_stderr")

    if result.returncode != 0:
        return PdfTextExtraction("", "pdftotext", warnings, [])

    text = normalize_text(result.stdout.decode("utf-8", errors="replace"))
    if not text.strip():
        warnings.append("pdftotext_empty_text")

    html_urls, html_warnings = extract_pdf_urls_with_pdftohtml(path)
    warnings.extend(html_warnings)
    return PdfTextExtraction(text, "pdftotext", warnings, unique_urls(extract_urls(text) + html_urls))


def normalize_text(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def preview_text(text: str, max_chars: int = 500) -> str:
    compact = "\n".join(line.rstrip() for line in text.splitlines())
    compact = compact.strip()
    if len(compact) <= max_chars:
        return compact
    return compact[:max_chars].rstrip() + "..."


def extract_urls(text: str) -> list[str]:
    matches = re.findall(r"https?://[^\s\"'<>]+", text)
    return unique_urls(clean_extracted_url(match) for match in matches)


def extract_pdf_urls_with_pdftohtml(path: Path) -> tuple[list[str], list[str]]:
    warnings: list[str] = []
    try:
        result = subprocess.run(
            ["pdftohtml", "-xml", "-stdout", str(path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except FileNotFoundError:
        return [], ["pdftohtml_not_found"]

    if result.returncode != 0:
        warnings.append(f"pdftohtml_exit:{result.returncode}")
    if result.stderr:
        warnings.append("pdftohtml_stderr")

    xml_text = result.stdout.decode("utf-8", errors="replace")
    hrefs = re.findall(r'href="([^"]+)"', xml_text)
    urls = [clean_extracted_url(unescape(href)) for href in hrefs if href.startswith(("http://", "https://"))]
    return unique_urls(urls), warnings


def clean_extracted_url(url: str) -> str:
    return url.strip().rstrip("。；;,，")


def unique_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def unique_urls(urls: list[str] | object) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for url in urls:
        if not isinstance(url, str):
            continue
        if url and url not in seen:
            seen.add(url)
            result.append(url)
    return result
