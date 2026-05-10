---
name: hello-world
description: 按名字向用户打招呼，并演示技能激活机制。当用户说 hello、hi、你好，或明确要求测试技能系统时使用。
---

# Hello World Skill

此技能用于验证技能激活和 bash 命令执行是否正常工作。

## 使用方法

1. 从用户消息中提取名字（如果未提供名字，默认为"朋友"）
2. 执行打招呼脚本：

       bash: python skills/hello-world/scripts/hello.py "<name>"

3. 将脚本的输出返回给用户

## 示例

用户: "你好，我叫小明"
Action: `python skills/hello-world/scripts/hello.py "小明"`
Output: `你好，小明！Mini Agent 已经正常运作。`
Response to user: 你好，小明！Mini Agent 已经正常运作。