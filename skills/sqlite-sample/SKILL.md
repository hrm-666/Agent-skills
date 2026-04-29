---
name: sqlite-sample
description: Query the employee database for information like salaries, departments, or specific hire dates. Use this when the user asks about staff, payroll, or department statistics.
---

# SQLite Sample Skill

This skill queries the `employees` table in `data/sample.db`.

## Schema

Table: `employees`
- `id`: Integer primary key
- `name`: Text
- `department`: Text
- `salary`: Real
- `hire_date`: Text, formatted as YYYY-MM-DD

## How to use

1. Formulate one valid SQL `SELECT` query based on the user's request.
2. Execute the query with the bash tool:

       python skills/sqlite-sample/scripts/query.py --sql "SELECT ..."

3. If the command returns JSON rows, present those rows directly to the user in a concise natural-language answer. Do not inspect the database again unless the command returns an explicit error.

## Constraints

- Only `SELECT` queries are allowed.
- Maximum `LIMIT` is 100.
- Do not perform updates, inserts, deletes, drops, or filesystem cleanup.

## Examples

User: "查询薪资最高的3个员工"

Action:

       python skills/sqlite-sample/scripts/query.py --sql "SELECT name, salary, department FROM employees ORDER BY salary DESC LIMIT 3"

Response: summarize the three returned employees.

User: "Engineering 部门有多少人？"

Action:

       python skills/sqlite-sample/scripts/query.py --sql "SELECT COUNT(*) AS count FROM employees WHERE department='Engineering'"

Response: provide the count.
