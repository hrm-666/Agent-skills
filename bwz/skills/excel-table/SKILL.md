---
name: excel-table
description: Analyze uploaded Excel workbooks or spreadsheet tables. Use when the user asks about xlsx files, Excel data, salary rankings, top rows, or sorting spreadsheet columns.
---

# Excel Table Skill

Use this skill for Excel workbooks uploaded through WebUI or stored in the project.

## When to Use

Use this skill when the user asks to:

- Read an Excel file
- Find top or bottom rows by a column
- Rank employees by salary from a workbook
- Inspect workbook sheets or table columns

Do not use the built-in `read` tool for `.xlsx` files because they are binary files.

## Script

Run the helper script from the project root:

```bash
python skills/excel-table/scripts/query.py --file "uploads/xlsx-e2337157c59f" --top-by "月薪" --limit 3
```

The script can read WebUI uploads even if the uploaded filename lost its `.xlsx` extension.

## Common Commands

Find the three highest monthly salaries:

```bash
python skills/excel-table/scripts/query.py --file "uploads/xlsx-e2337157c59f" --top-by "月薪" --limit 3
```

List sheets and columns:

```bash
python skills/excel-table/scripts/query.py --file "uploads/xlsx-e2337157c59f" --list-columns
```

Use a specific sheet:

```bash
python skills/excel-table/scripts/query.py --file "uploads/xlsx-e2337157c59f" --sheet "员工薪资数据" --top-by "月薪" --limit 3
```

## Rules

- Always use this script instead of multi-line `python -c` commands.
- Quote file paths.
- Prefer paths under `uploads/` when the user attached a file.
- After the script returns JSON, answer the user directly from the `rows` array.
