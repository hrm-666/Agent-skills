---
name: sqlite-sample
description: Query the sample SQLite employee database for read-only analysis tasks such as rankings, averages, and employee lookup.
---

# SQLite Sample Skill

Use this skill when the user asks questions about the sample employee database,
including employee lookup, salary ranking, department statistics, or hire date
analysis.

The database is `data/sample.db`. See the table schema in
`skills/sqlite-sample/references/schema.md`.

## How to use

1. Translate the user's question into one safe SQLite SELECT statement.
2. Run the query script with bash:

       python skills/sqlite-sample/scripts/query.py --sql "SELECT name, department, salary FROM employees ORDER BY salary DESC LIMIT 3"

3. Read the JSON output and answer the user in concise Chinese.

## Safety rules

- Only SELECT statements are allowed.
- Do not write INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, PRAGMA, or multiple SQL statements.
- If the user asks to modify data, explain that this sample skill is read-only.
- If the query may return many rows, add an explicit LIMIT.

## Schema

Table: `employees`

| Column | Type | Meaning |
| --- | --- | --- |
| id | INTEGER | Employee id |
| name | TEXT | Employee name |
| department | TEXT | Department name |
| salary | INTEGER | Monthly salary |
| hire_date | TEXT | Hire date, formatted as YYYY-MM-DD |

## Examples

Question: "查询薪资最高的3个员工"

Run:

    python skills/sqlite-sample/scripts/query.py --sql "SELECT name, department, salary FROM employees ORDER BY salary DESC LIMIT 3"

Question: "各部门平均工资是多少"

Run:

    python skills/sqlite-sample/scripts/query.py --sql "SELECT department, ROUND(AVG(salary), 2) AS avg_salary FROM employees GROUP BY department ORDER BY avg_salary DESC"

Question: "查一下张敏的信息"

Run:

    python skills/sqlite-sample/scripts/query.py --sql "SELECT id, name, department, salary, hire_date FROM employees WHERE name = '张敏' LIMIT 1"
