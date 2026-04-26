---
name: sqlite-sample
description: Query the sample SQLite employee database for read-only analysis tasks such as rankings, averages, and employee lookup.
---

# SQLite Sample Skill

Use this skill when the user asks about employee data stored in the local SQLite database.

This skill is for read-only database analysis only.

Examples:

- Find the top 10 highest paid employees
- Calculate the average salary by department
- Search for an employee by name
- Count how many employees are in each department
- View employee records for verification

Before querying, check the database structure here:

`skills/sqlite-sample/references/schema.md`

Always activate the skill first:

```python
activate_skill("sqlite-sample")
```

Use bash to run queries like these:

```bash
python skills/sqlite-sample/scripts/query.py --sql "SELECT * FROM employees LIMIT 5"
```

```bash
python skills/sqlite-sample/scripts/query.py --sql "SELECT name, salary FROM employees ORDER BY salary DESC LIMIT 10"
```

```bash
python skills/sqlite-sample/scripts/query.py --sql "SELECT department, AVG(salary) FROM employees GROUP BY department"
```

```bash
python skills/sqlite-sample/scripts/query.py --sql "SELECT COUNT(*) FROM employees"
```

## Rules

- Only `SELECT` statements are allowed
- Do not use INSERT, UPDATE, DELETE, DROP, or ALTER
- Prefer simple and clear SQL queries
- If table or column names are unknown, read `schema.md` first
- Summarize results clearly for the user instead of pasting large raw outputs directly

## If a query fails

1. Check table and column names
2. Simplify the SQL statement
3. Retry with a smaller query first