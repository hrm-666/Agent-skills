---
name: sqlite-sample
description: Query the sample employee SQLite database in data/sample.db. Use when the user asks about employees, salaries, departments, top earners, or department-level salary statistics.
---

# SQLite Sample Skill

This skill is used for querying the sample employee database at `data/sample.db`.

## When to use

Use this skill when the user wants to:

- Find specific employees
- Compare salaries
- Rank employees by salary
- Calculate department-level statistics

## Database

- Database path: `data/sample.db`
- Main table: `employees`
- Schema reference: `references/schema.md`

## How to run

Use the query script with a `SELECT` statement:

```bash
python skills/sqlite-sample/scripts/query.py --sql "SELECT name, salary FROM employees ORDER BY salary DESC LIMIT 3"
```

## Safety rule

- Only `SELECT` queries are allowed
- Do not use `INSERT`, `UPDATE`, `DELETE`, `DROP`, or any schema-changing SQL

## Query examples

Top 3 highest-paid employees:

```bash
python skills/sqlite-sample/scripts/query.py --sql "SELECT name, salary FROM employees ORDER BY salary DESC LIMIT 3"
```

Average salary by department:

```bash
python skills/sqlite-sample/scripts/query.py --sql "SELECT department, AVG(salary) AS avg_salary FROM employees GROUP BY department ORDER BY avg_salary DESC"
```

Find one employee by name:

```bash
python skills/sqlite-sample/scripts/query.py --sql "SELECT id, name, department, salary, hire_date FROM employees WHERE name = '张伟'"
```
