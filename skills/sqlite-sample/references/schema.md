# Employees Schema

Database file:

- `data/sample.db`

Main table:

- `employees`

## Table definition

| Column | Type | Meaning |
| --- | --- | --- |
| `id` | `INTEGER` | Employee primary key |
| `name` | `TEXT` | Employee name |
| `department` | `TEXT` | Department name |
| `salary` | `INTEGER` | Monthly salary |
| `hire_date` | `TEXT` | Hire date in `YYYY-MM-DD` format |

## Query guidance

- Use `ORDER BY salary DESC` to rank high-salary employees
- Use `GROUP BY department` with `AVG(salary)` to compare departments
- Use `WHERE name = '...'` to find one employee
- Keep queries read-only and limited to `SELECT`

## Example queries

Top earners:

```sql
SELECT name, salary
FROM employees
ORDER BY salary DESC
LIMIT 3;
```

Department salary summary:

```sql
SELECT department, AVG(salary) AS avg_salary
FROM employees
GROUP BY department
ORDER BY avg_salary DESC;
```

Employee detail:

```sql
SELECT id, name, department, salary, hire_date
FROM employees
WHERE name = '张伟';
```
