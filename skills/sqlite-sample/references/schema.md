# employees 表结构

## 字段说明

| 列名 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键，自增 |
| name | TEXT | 姓名 |
| department | TEXT | 部门 |
| salary | INTEGER | 工资 |
| hire_date | TEXT | 入职日期 |

## 示例数据

| id | name | department | salary | hire_date |
|----|------|------------|--------|------------|
| 1 | 张敏 | Engineering | 32000 | 2021-03-15 |
| 2 | 李娜 | Engineering | 29500 | 2022-07-10 |
| 3 | 王磊 | Sales | 26000 | 2020-09-01 |
| 4 | 赵静 | Sales | 24000 | 2023-01-08 |
| 5 | 陈晨 | HR | 21000 | 2019-11-12 |
| 6 | 刘洋 | Finance | 28000 | 2021-06-18 |
| 7 | 黄杰 | Finance | 30500 | 2018-04-22 |
| 8 | 周婷 | Operations | 23000 | 2022-02-14 |
| 9 | 吴昊 | Operations | 22500 | 2024-05-20 |
| 10 | 孙悦 | Marketing | 25000 | 2020-12-03 |

## 常用查询示例

```sql
-- 各部门平均工资
SELECT department, AVG(salary) as avg_salary FROM employees GROUP BY department;

-- 工资最高的3人
SELECT name, department, salary FROM employees ORDER BY salary DESC LIMIT 3;

-- 2022年后入职的员工
SELECT name, department, hire_date FROM employees WHERE hire_date > '2022-01-01';

-- 按部门筛选
SELECT * FROM employees WHERE department = 'Engineering';