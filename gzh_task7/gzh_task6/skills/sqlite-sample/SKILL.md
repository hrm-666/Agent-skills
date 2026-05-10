---
name: sqlite-sample
description: 查询包含员工数据的示例 SQLite 数据库。当用户询问员工信息查询、薪资统计、部门分析或任何针对示例数据库的 SQL 查询时，使用此技能。
---

# SQLite 示例技能

此技能提供对示例 SQLite 数据库（`data/sample.db`）的访问，数据库中包含 `employees`（员工）表。

## 数据库表结构

`employees` 表包含以下字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| name | TEXT | 员工姓名 |
| department | TEXT | 所属部门 |
| salary | INTEGER | 年薪（美元） |
| hire_date | TEXT | 入职日期，格式为 YYYY-MM-DD |

## 使用方法

1. 首先使用 `activate_skill` 激活此技能。

2. 使用 bash 工具配合查询脚本查询数据库：

       python skills/sqlite-sample/scripts/query.py --sql "SELECT * FROM employees LIMIT 10"

3. 脚本输出为 JSON 格式：

       {"success": true, "count": 10, "rows": [...]}

   如果发生错误：

       {"success": false, "error": "错误信息"}

## 查询示例

查询薪资最高的 3 名员工：

    SELECT name, salary, department FROM employees ORDER BY salary DESC LIMIT 3

按部门统计平均薪资：

    SELECT department, AVG(salary) as avg_salary FROM employees GROUP BY department

按姓名查找员工：

    SELECT * FROM employees WHERE name LIKE '%关键字%'

## 安全说明

查询脚本只允许 SELECT 语句。任何其他 SQL 命令（如 DROP、INSERT、UPDATE、DELETE）都将被拒绝。