---
name: mysql-api-ingestor
description: Fetch JSON data from a user-provided API URL, clean flexible nested records such as PledgeBox orders, store them in MySQL, and preview imported rows. Use when the user asks to import API link data into MySQL, clean order data, persist complex JSON, or inspect stored API import results.
---

# MySQL API Ingestor

Use this skill to fetch a JSON API URL, normalize records, and store them in MySQL while preserving the complete original JSON.

## Required environment

Read MySQL settings from `.env`:

    MYSQL_HOST=localhost
    MYSQL_PORT=3306
    MYSQL_USER=root
    MYSQL_PASSWORD=
    MYSQL_DATABASE=mini_agent_data

Install dependencies from `requirements.txt` if the script reports a missing package.

## Import workflow

Run:

    python skills/mysql-api-ingestor/scripts/import_url.py "https://example.com/api"

The script will:

1. Fetch JSON from the URL.
2. Mask sensitive query parameters in logs and import job metadata.
3. Detect records from common containers such as `data`, `orders`, `results`, `records`, or a top-level list.
4. Create MySQL tables if needed.
5. Store common order fields in `api_orders`.
6. Store shipping addresses in `api_order_addresses`.
7. Store reward items, addons, gifts, and addon child items in `api_order_line_items`.
8. Store dynamic fields, variants, questions, and unrecognized nested attributes in `api_order_attributes`.
9. Preserve every source record in `raw_json`.

## Preview workflow

Run:

    python skills/mysql-api-ingestor/scripts/preview_data.py

Optional:

    python skills/mysql-api-ingestor/scripts/preview_data.py --job-id 12 --table api_orders --limit 10

## Data strategy

- Prefer stable columns for common fields.
- Store inconsistent or deeply nested fields as attributes.
- Never discard unknown fields; keep them in `raw_json`.
- Treat PledgeBox `/api/openapi/orders` responses as a first-class structure, but fall back to generic JSON handling for other APIs.
- Do not print full API tokens. Use masked URLs in user-facing answers.
