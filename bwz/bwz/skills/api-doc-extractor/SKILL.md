---
name: api-doc-extractor
description: Extract endpoint URLs and request parameters from API documents, build read-only GET requests, fetch API data, and normalize JSON responses into Markdown, CSV, or JSON. Use when the user asks to read an API PDF/Markdown/txt document, stitch parameters from tables into a request URL, enter the documented endpoint, extract returned fields, or organize API data.
---

# API Doc Extractor

Use this skill to turn an API document into a deterministic read-only data extraction workflow.

## Default workflow

1. Identify the API document path from the user request.
2. Run the entry script:

       python skills/api-doc-extractor/scripts/run.py --doc "<document-path>" --format markdown --dry-run

3. Inspect the request plan. For GET endpoints, the main path is:

       method-row endpoint + values extracted from the request parameter table

4. Treat example URLs or example JSON blocks as optional fallback and validation sources only.
5. If required parameter values are missing, ask the user for those values instead of guessing.
6. Do not execute POST, PUT, PATCH, or DELETE requests unless the user explicitly confirms.

## Output formats

Use `--format markdown`, `--format csv`, or `--format json`.

## Notes

- Keep tokens, API keys, secrets, and passwords masked in user-facing summaries.
- Skip optional parameters unless the document or user provides a value.
- Preserve nested response paths with dot notation and `[]` for arrays, such as `reward.items[].sku`.
