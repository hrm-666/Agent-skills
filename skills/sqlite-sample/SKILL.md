---
name: sqlite-sample
description: Query the employee database for information like salaries, departments, or specific hire dates. Use this when the user asks about staff, payroll, or department statistics.
---

# SQLite Sample Skill

This skill allows querying the `employees` table in the sample database.

## Schema

Table: `employees`
- `id`: Integer (Primary Key)
- `name`: Text
- `department`: Text
- `salary`: Real
- `hire_date`: Text (YYYY-MM-DD)

## How to use

1. Formulate a valid SQL SELECT query based on the user's request.
2. Execute the query using the bash tool:

       bash: python skills/sqlite-sample/scripts/query.py --sql "SELECT ..."

3. Present the JSON results to the user.

## Constraints

- ONLY SELECT queries are allowed.
- Maximum LIMIT is 100.
- Do not perform updates or deletes.

## Examples

User: "谁的工资最高？"
Action: `python skills/sqlite-sample/scripts/query.py --sql "SELECT name, salary FROM employees ORDER BY salary DESC LIMIT 1"`

User: "研发部有多少人？"
Action: `python skills/sqlite-sample/scripts/query.py --sql "SELECT count(*) FROM employees WHERE department='研发部'"`
