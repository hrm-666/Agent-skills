---
name: hello-world
description: Greet the user by name and demonstrate the skill activation mechanism. Use when user says hello, hi, 你好, or asks to test skills.
---

# Hello World Skill

This skill verifies that skill activation and bash execution work correctly.

## How To Use

1. Extract the user's name from their message (default to "朋友").
2. Run: `python skills/hello-world/scripts/hello.py "<name>"`
3. Return the script output as the final response.

## Example

User: "你好,我叫小明"
Action: `python skills/hello-world/scripts/hello.py "小明"`
Output: `你好,小明!Mini Agent 已经正常运作。`
