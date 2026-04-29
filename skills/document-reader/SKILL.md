---
name: document-reader
description: Read PDF, Word docx, txt, or markdown files and extract their text content. Use this when the user uploads or asks about documents.
---

# Document Reader Skill

Use this skill to inspect uploaded documents.

## How to use

Run:

    python skills/document-reader/scripts/read_doc.py "uploads/file.pdf"

Supported formats: `.pdf`, `.docx`, `.txt`, `.md`.

## Response rules

- Summarize the extracted content in Chinese unless the user asks otherwise.
- Quote only short snippets.
- If extraction fails or a dependency is missing, explain the exact issue.
