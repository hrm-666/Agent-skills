# employees

The sample database is `data/sample.db`.

Table: `employees`

| Column | Type | Description |
| --- | --- | --- |
| id | INTEGER PRIMARY KEY AUTOINCREMENT | Employee id |
| name | TEXT NOT NULL | Employee name |
| department | TEXT NOT NULL | Department name |
| salary | INTEGER NOT NULL | Monthly salary |
| hire_date | TEXT NOT NULL | Hire date, formatted as YYYY-MM-DD |

Example rows:

| name | department | salary | hire_date |
| --- | --- | --- | --- |
| 张敏 | Engineering | 32000 | 2021-03-15 |
| 李娜 | Engineering | 29500 | 2022-07-10 |
| 王磊 | Sales | 26000 | 2020-09-01 |

Useful query patterns:

```sql
SELECT name, department, salary
FROM employees
ORDER BY salary DESC
LIMIT 3;
```

```sql
SELECT department, ROUND(AVG(salary), 2) AS avg_salary
FROM employees
GROUP BY department
ORDER BY avg_salary DESC;
```
