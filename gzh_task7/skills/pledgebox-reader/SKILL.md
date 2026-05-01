---
name: pledgebox-reader
description: "Query orders, backers, and shipping info from PledgeBox crowdfunding platform. Use when user asks: get orders, list backers, find order by email, check order status, show pledge statistics, export survey data, or any PledgeBox data query."
---

# PledgeBox Data Reader Skill

This skill reads data from PledgeBox platform via official OpenAPI.

## Prerequisite: Configuration

First-time use requires API token in `config.yaml`:

```yaml
pledgebox:
  api_token: "your_api_token_here"
  project_id: 100001
```

Get API token from: PledgeBox Dashboard → Settings → API

## Available Commands (use bash tool directly)

### 1. List all orders (completed)
```bash
python skills/pledgebox-reader/scripts/fetch_orders.py --completed
```

### 2. Find order by email
```bash
python skills/pledgebox-reader/scripts/fetch_orders.py --email "user@example.com"
```

### 3. Get order by PledgeBox ID
```bash
python skills/pledgebox-reader/scripts/fetch_orders.py --pbid "PBID003315433"
```

### 4. Filter by status (unlock/locked/shipped/refunded)
```bash
python skills/pledgebox-reader/scripts/fetch_orders.py --status "Locked"
```

### 5. Get campaign statistics (total backers, total amount, average)
```bash
python skills/pledgebox-reader/scripts/fetch_orders.py --stats
```

### 6. Export all orders to JSON file
```bash
python skills/pledgebox-reader/scripts/fetch_orders.py --export --output orders.json
```

### 7. List all orders (paginated, default page=1, limit=20)
```bash
python skills/pledgebox-reader/scripts/fetch_orders.py --list --page 1 --limit 20
```

## Output Format

All commands return JSON:

```json
{
  "success": true,
  "data": [...],
  "count": 10,
  "message": "Found 10 orders"
}
```

If error:

```json
{
  "success": false,
  "error": "Error message here"
}
```

## Examples

**User**: "Show me all completed orders from PledgeBox"

**Action**:
```bash
python skills/pledgebox-reader/scripts/fetch_orders.py --completed
```

**User**: "Find order for email demo@pledgebox.com"

**Action**:
```bash
python skills/pledgebox-reader/scripts/fetch_orders.py --email "demo@pledgebox.com"
```

**User**: "What's the total pledge amount?"

**Action**:
```bash
python skills/pledgebox-reader/scripts/fetch_orders.py --stats
```

## Notes

- API token and project_id must be configured before first use
- All operations are read-only (GET requests only)
- Results are automatically paginated, use --page to navigate