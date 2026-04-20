---
name: sqlite-sample
description: 查询示例 SQLite 数据库中的 employees 表，支持按薪资、部门等条件筛选。当用户询问员工、薪资、部门相关数据时使用。
---

# SQLite Sample Skill

查询 data/sample.db 中的 employees 表，仅允许 SELECT 语句。

## 表结构

字段：id, name, department, salary（月薪，元）, hire_date（YYYY-MM-DD）
部门：技术部、市场部、人事部、财务部、产品部

## 使用方法

    bash: python skills/sqlite-sample/scripts/query.py --sql "SELECT ..."

脚本返回 JSON 数组，解析后以自然语言回复用户。

## 常用查询示例

查询薪资最高的 3 名员工：

    bash: python skills/sqlite-sample/scripts/query.py --sql "SELECT name, department, salary FROM employees ORDER BY salary DESC LIMIT 3"

各部门平均薪资：

    bash: python skills/sqlite-sample/scripts/query.py --sql "SELECT department, AVG(salary) as avg_salary FROM employees GROUP BY department ORDER BY avg_salary DESC"

## 安全说明

脚本只接受以 select 开头的语句，其他操作一律拒绝。
