---
name: hello-world
description: Greet the user by name and demonstrate the skill activation mechanism. Use when the user says hello, hi, 你好, or explicitly asks to test the skill system.
---

# Hello World Skill

This skill exists to verify that skill activation and bash execution work correctly.

## How to use

1. Extract the user's name from their message. Default to "朋友" if not given.
2. Run the greeting script:

       python skills/hello-world/scripts/hello.py "<name>"

3. Return the script's output directly to the user.

## Example

User: "你好,我叫杨明山"
Action: `python skills/hello-world/scripts/hello.py "杨明山"`
Output: `你好,杨明山!Mini Agent 已经正常运作。`
Response: 你好,杨明山!Mini Agent 已经正常运作。
