---
name: api-extractor
description: Extract GET endpoint URLs and request parameters from API documents (PDF/Markdown/TXT), fetch JSON data, and normalize results into Markdown, CSV, or JSON. Use when the user asks to read an API document, fetch data from a documented GET endpoint, or organize API response fields into a table.
---

# API Extractor

Use this skill to turn an API document into a deterministic read-only data extraction workflow.

## Default workflow

1. Identify the API document path from the user request.
2. Run the entry script (dry-run first to inspect the request plan):

       python skills/api-extractor/scripts/run.py --doc "<path>" --dry-run

3. If the dry-run shows `missing_required_params`, ask the user for those parameter values. Then re-run with `--param`:

       python skills/api-extractor/scripts/run.py --doc "<path>" --format markdown --param api_token=xxx --param project_id=100001

4. If the request plan looks correct and all required params are provided, re-run without `--dry-run` to fetch data:

       python skills/api-extractor/scripts/run.py --doc "<path>" --format markdown

5. Report the result summary to the user. Point them to the exported file path.

## CLI reference

```
python skills/api-extractor/scripts/run.py --doc <path> [options]

Options:
  --doc PATH         API document path (PDF/MD/TXT) [required]
  --format FMT       Output format: markdown | csv | json [default: markdown]
  --param KEY=VALUE  Pass parameter values (repeatable). Example:
                       --param api_token=xxx --param project_id=100001
  --output PATH      Custom export path (optional)
  --timeout SEC      HTTP timeout in seconds [default: 30]
  --dry-run          Parse only, show the request plan without fetching
```

## Rules

- Only GET endpoints are executed. POST/PUT/PATCH/DELETE are parsed but skipped.
- If `missing_required_params` is non-empty, stop and ask the user for those values.
- Use `--param key=value` (can be repeated) to pass user-provided parameter values.
- Tokens and secrets in output are automatically masked.
- Raw API responses are saved to `workspace/api-extractor/raw/`.
- Exported files go to `workspace/api-extractor/exports/`.

## Output formats

Use `--format markdown`, `--format csv`, or `--format json`.
