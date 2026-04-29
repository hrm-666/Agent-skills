---
name: spreadsheet-reader
description: Read Excel or CSV files and summarize sheets, columns, rows, and sample records. Use this when the user uploads or asks about .xlsx, .xlsm, or .csv files.
---

# Spreadsheet Reader Skill

Use this skill to inspect uploaded spreadsheet files.

## How to use

Run:

    python skills/spreadsheet-reader/scripts/read_sheet.py "uploads/file.xlsx"

For CSV files, use the same command.

## Response rules

- Summarize sheet names, row counts, columns, and notable values.
- If the user asks for a specific metric, compute it from the extracted rows when possible.
- If the script reports a missing dependency, tell the user to install `requirements.txt`.
