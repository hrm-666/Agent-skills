---
name: sqlite-sample
description: Query the sample SQLite employee database for read-only analysis tasks such as rankings, averages, and employee lookup.
---

# SQLite Sample Skill

See `skills/sqlite-sample/references/schema.md`.

Run:

    python skills/sqlite-sample/scripts/query.py --sql "SELECT * FROM employees LIMIT 5"

Only SELECT statements are allowed.
