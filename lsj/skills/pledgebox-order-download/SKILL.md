---
name: pledgebox-order-download
description: Download PledgeBox crowdfunding order data by project ID, save raw JSON, and export normalized CSV tables for orders, order items, questions, run summary, and errors.
---

# PledgeBox Order Download

Use this skill when the user needs to download order data from the PledgeBox OpenAPI for an overseas crowdfunding project and save it locally for later cleaning or shipping-template conversion.

## Scope

This is a first-stage data acquisition skill. It downloads and structures source data only.

Do:

- Call `GET https://api.pledgebox.com/api/openapi/orders`.
- Save the complete raw API response as JSON.
- Export separate CSV tables instead of combining nested order data into one wide table.
- Preserve order, address, reward item, addon, gift, and question data where present.

Do not:

- Clean or correct shipping addresses.
- Validate zip codes, states, cities, or country rules.
- Merge product bundles.
- Calculate customs declaration prices.
- Generate a final domestic shipping or ecommerce import template.

## Inputs

- `project_id`: Required PledgeBox project ID.
- `api_token`: Required API token. Prefer environment variable `PLEDGEBOX_API_TOKEN`; `--api-token` is also supported.
- `is_completed`: Optional, default `1` to download completed survey orders.
- `order_status`: Optional, default `lock` to download locked orders. Pass an empty value if all statuses are needed.
- `output_dir`: Optional, default `workspace/pledgebox_exports`.
- `max_pages`: Optional, default `100`.

The token must not be committed to source control. If the token came from a PDF and contains line breaks, the script removes whitespace before sending the request.

## How To Use

From the `D:\Agent\Agent-skills` repo:

```powershell
$env:PLEDGEBOX_API_TOKEN="your-token"
python skills/pledgebox-order-download/scripts/download_orders.py --project-id 100001
```

With explicit options:

```powershell
python skills/pledgebox-order-download/scripts/download_orders.py `
  --project-id 100001 `
  --api-token "your-token" `
  --is-completed 1 `
  --order-status lock `
  --output-dir "workspace/pledgebox_exports" `
  --max-pages 100
```

## Outputs

Files are written under:

```text
workspace/pledgebox_exports/<project_id>/
```

- `raw_orders_<project_id>.json`: Complete raw order records returned by the API.
- `orders_<project_id>.csv`: One row per order.
- `order_items_<project_id>.csv`: One row per reward item, addon, or gift.
- `questions_<project_id>.csv`: One row per reward/item/addon question.
- `run_summary_<project_id>.csv`: Counts, filters, page information, and output paths.
- `errors_<project_id>.csv`: API, parsing, and row-level warnings.

## Notes

The API response is nested. `shipping_address` is flattened into the order table. `reward.items`, `addons`, and `gifts` are exported to `order_items` with `item_source` set to `reward_item`, `addon`, or `gift`.
