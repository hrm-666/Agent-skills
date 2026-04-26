```markdown
# Mini Agent

一个极简的 Python Agent 框架，遵循 [agentskills.io](https://agentskills.io) 开放标准。

## 5 分钟快速开始

### 1. 环境准备

```bash

# 创建虚拟环境
python -m venv .venv

# 激活虚拟环境
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置 API Key

复制 `.env.example` 为 `.env`，填入你使用的 API Key：

```bash
cp .env.example .env
```

编辑 `.env` 文件：

```ini
MOONSHOT_API_KEY=你的Kimi密钥
# 或
DEEPSEEK_API_KEY=你的DeepSeek密钥
# 或
DASHSCOPE_API_KEY=你的通义千问密钥
```

### 3. 初始化示例数据库

```bash
python main.py setup
```

### 4. 运行

**命令行模式**：

# 单次执行
```bash
python main.py cli "你好，我叫小明"
```

# 交互模式
```bash
python main.py cli --interactive
```

# WebUI 模式
```bash
python main.py webui
```
浏览器打开 `http://127.0.0.1:8000`

# powershell运行
```bash
.venv\Scripts\python.exe main.py cli "你好我叫小明"
```

### 5. 测试 Skill


# 测试 hello-world skill
```bash
python main.py cli "你好"
```

# 测试数据库查询 skill
```bash
python main.py cli "查询薪资最高的3个员工"
```

## 目录说明

```
mini-agent/
├── core/                    # 核心引擎
│   ├── agent.py            # Agent 主循环
│   ├── llm.py              # LLM 抽象层（Kimi/Qwen/DeepSeek）
│   ├── skills.py           # Skill 扫描和加载
│   └── tools.py            # 工具注册表
│
├── tools_builtin/           # 内置工具
│   ├── file_ops.py         # read / write
│   ├── shell.py            # bash
│   └── skill_ops.py        # activate_skill
│
├── skills/                  # 可插拔 Skills 目录
│   ├── hello-world/        # 示例 Skill：打招呼
│   └── sqlite-sample/      # 示例 Skill：数据库查询
│
├── adapters/                # 入口适配器
│   ├── cli.py              # 命令行入口
│   └── server.py           # WebUI 服务
│
├── webui/                   # 前端文件
│   └── index.html          # 单文件 Web 界面
│
├── data/                    # 数据目录
│   └── sample.db           # 示例 SQLite 数据库
│
├── logs/                    # 日志目录（自动生成）
├── uploads/                 # 上传文件目录（自动生成）
│
├── config.yaml              # 配置文件
├── main.py                  # 统一入口
└── requirements.txt         # 依赖列表
```

## 配置文件

编辑 `config.yaml` 可调整以下配置：

```yaml
# 当前使用的模型
active_provider: kimi

# 模型覆盖（不填则使用默认模型）
providers:
  kimi:
    model: kimi-k2.5
  deepseek:
    model: deepseek-chat

# Skill 配置
skills:
  dir: ./skills
  enabled: null        # null=全部启用，或填白名单数组

# Agent 配置
agent:
  max_iterations: 15

# WebUI 配置
webui:
  host: 127.0.0.1
  port: 8000
```


## 如何添加新 Skill

### 步骤 1：创建目录结构

```
skills/
└── your-skill-name/
    ├── SKILL.md
    └── scripts/
        └── your_script.py
```

### 步骤 2：编写 SKILL.md

```
---
name: your-skill-name
description: 用一句话描述这个技能的功能和使用场景（不超过1024字符，不能包含尖括号）
---
```

# 技能标题

## 使用方法

通过 bash 工具执行脚本：

```bash
python skills/your-skill-name/scripts/your_script.py --参数名 参数值
```

## 参数说明

| 参数 | 说明 |
|------|------|
| --param1 | 参数1的说明 |
| --param2 | 参数2的说明 |

## 返回格式

```json
{
  "success": true,
  "data": "返回的数据"
}
```

## 示例

```bash
python skills/your-skill-name/scripts/your_script.py --name "张三"
```


### 步骤 3：编写脚本

`scripts/your_script.py` 示例：

```python
#!/usr/bin/env python3
import argparse
import json

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", type=str, required=True)
    args = parser.parse_args()
    
    result = {"success": True, "data": f"Hello, {args.name}"}
    print(json.dumps(result, ensure_ascii=False))

if __name__ == "__main__":
    main()
```

### 步骤 4：验证

重启 Agent 后执行：

```bash
python main.py cli "你的测试问题"
```

Agent 会自动扫描 `skills/` 目录，根据 `SKILL.md` 的描述判断何时调用你的技能。

### Skill 规范要求

| 规则 | 要求 |
|------|------|
| 文件名 | 必须为 `SKILL.md`（大小写敏感） |
| `name` | 小写字母/数字/连字符，≤64字符，不能以连字符开头/结尾，不能有连续连字符 |
| `description` | ≤1024字符，不能包含 `<` 或 `>` |
| 可选字段 | `license`、`compatibility`、`metadata` |
```