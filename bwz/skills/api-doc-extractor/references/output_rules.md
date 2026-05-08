# Output Rules

## Markdown

Use Markdown for short previews. Limit preview rows by default and point to exported files when full output is large.

## CSV

Use UTF-8 with BOM so spreadsheet tools can open Chinese text cleanly.

## JSON

Keep structured data for follow-up automation and debugging.

## Field flattening

- Top-level fields keep their original names.
- Nested object fields use dot notation.
- Array fields use `[]`.
- Join array values with `; ` unless the user asks to expand arrays into rows.
