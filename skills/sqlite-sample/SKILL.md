---
name: sqlite-sample
description: Query the sample SQLite employee database for analytics and lookup tasks. Use for salary, department, and employee queries.
---

# SQLite Sample Skill

Use this skill when the user asks about employee salary, department distribution, or hire date statistics.

## Data Source

- Database path: `data/sample.db`
- Table: `employees`
- Reference schema: `skills/sqlite-sample/references/schema.md`

## How To Use

1. Convert the user request into a safe SQL SELECT query.
2. Execute the query:
   `python skills/sqlite-sample/scripts/query.py --sql "SELECT ..."`
3. Return concise findings based on JSON output.

## Safety Rules

- Only SELECT is allowed.
- LIMIT 100 is applied by default when LIMIT is missing.
- Do not run UPDATE/DELETE/INSERT/DDL statements.

## Examples

- Top salaries:
  `python skills/sqlite-sample/scripts/query.py --sql "SELECT name, salary FROM employees ORDER BY salary DESC LIMIT 3"`
- Average salary by department:
  `python skills/sqlite-sample/scripts/query.py --sql "SELECT department, AVG(salary) AS avg_salary FROM employees GROUP BY department"`
