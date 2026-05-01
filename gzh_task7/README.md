# Mini Agent

一个遵循 [agentskills.io](https://agentskills.io) 开放标准的轻量级 AI Agent 框架。

## 功能特性

- 🔧 **极简工具集**：内置 read / write / bash / activate_skill 四个核心工具
- 🧠 **智能记忆**：支持无记忆、有限记忆、永久记忆三种模式
- 📦 **Skills 即插即用**：放入 `skills/` 目录即可自动加载
- 🌊 **流式输出**：支持 SSE 流式响应，逐字显示
- 🖥️ **双模式交互**：支持命令行 (CLI) 和网页 (WebUI) 两种交互方式
- 📎 **文件上传**：WebUI 支持拖拽上传文件（图片、文档等）
- 🔀 **多模型支持**：兼容 Kimi、Qwen、DeepSeek 三家 OpenAI 兼容接口

## 快速开始

### 1. 环境要求

- Python 3.10+
- pip

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置 API Key

复制 `.env.example` 为 `.env`，填入你的 API Key：

```bash
cp .env.example .env
```

编辑 `.env` 文件：

```env
MOONSHOT_API_KEY=your_kimi_api_key
DASHSCOPE_API_KEY=your_qwen_api_key
DEEPSEEK_API_KEY=your_deepseek_api_key
```

### 4. 初始化示例数据库（可选）

```bash
python main.py setup
```

### 5. 启动

**命令行模式：**

```bash
# 交互式对话
python main.py cli -i

# 单次执行
python main.py cli "你好，介绍一下你自己"
```

**WebUI 模式：**

```bash
python main.py webui
```

浏览器访问 `http://127.0.0.1:8000`

## 项目结构

```
mini-agent/
├── core/                    # 核心模块
│   ├── agent.py            # Agent 主循环
│   ├── llm.py              # LLM 抽象层
│   ├── skills.py           # Skill 扫描与加载
│   ├── tools.py            # 工具注册表
│   └── memory.py           # 对话记忆管理
├── tools_builtin/          # 内置工具
│   ├── file_ops.py         # read / write
│   ├── shell.py            # bash
│   └── skill_ops.py        # activate_skill
├── skills/                 # Skills 目录（可插拔）
│   ├── hello-world/        # 示例 Skill
│   ├── pledgebox-reader/   # PledgeBox 数据读取 Skill
│   └── sqlite-sample/      # SQLite 示例 Skill
├── adapters/               # 适配器
│   ├── cli.py              # 命令行界面
│   └── server.py           # FastAPI 服务
├── webui/                  # Web 界面
│   └── index.html          # 单文件前端
├── data/                   # 数据目录
├── logs/                   # 日志目录
├── uploads/                # 上传文件目录
├── config.yaml             # 主配置文件
├── .env                    # 密钥配置
├── main.py                 # 统一入口
└── requirements.txt        # 依赖列表
```

## 配置文件

### config.yaml

```yaml
# 当前启用的 LLM
active_provider: kimi

# Provider 配置
providers:
  kimi:
    model: kimi-k2.5
  qwen:
    model: qwen-vl-max
  deepseek:
    model: deepseek-chat

# Skills 配置
skills:
  dir: ./skills
  enabled: null  # null = 全部启用，或填白名单数组

# Agent 配置
agent:
  max_iterations: 15

# WebUI 配置
webui:
  host: 127.0.0.1
  port: 8000
```

## 内置工具

| 工具 | 功能 |
|------|------|
| `read` | 读取文本文件 |
| `write` | 写入文件（仅限 workspace/、uploads/、logs/、data/） |
| `bash` | 执行 Shell 命令 |
| `activate_skill` | 加载 Skill 的完整指令 |

## 记忆功能

支持三种记忆模式：

| 模式 | 说明 |
|------|------|
| **无记忆** | 每次对话独立，不记住之前的内容 |
| **有限记忆** | 记住最近 N 轮对话（可配置 N 值） |
| **永久记忆** | 记住所有对话，保存到文件，重启后保留 |

**CLI 命令：**
- `memory` - 查看记忆状态和内容
- `clear` - 清空当前记忆

**WebUI：**
- 点击右下角 🧠 按钮打开记忆配置弹窗

## 添加新 Skill

1. 在 `skills/` 目录下创建新文件夹，如 `skills/my-skill/`
2. 创建 `SKILL.md` 文件，包含 YAML frontmatter：

```markdown
---
name: my-skill
description: 简短描述这个 Skill 的功能和触发场景
---

# My Skill

## 使用说明

1. 执行命令：
   bash: python skills/my-skill/scripts/run.py

## 示例

用户："触发我的技能"
操作：bash python skills/my-skill/scripts/run.py
```

3. 在 `scripts/` 目录下放置实现脚本
4. 重启 Agent，Skill 自动生效

## 命令行使用

```bash
# 查看帮助
python main.py --help

# 交互式 CLI
python main.py cli -i

# 单次执行
python main.py cli "查询今天的天气"

# 启动 WebUI
python main.py webui

# 初始化示例数据库
python main.py setup
```

## 日志

日志文件保存在 `logs/agent-YYYY-MM-DD.log`，同时输出到控制台（使用 rich 彩色输出）。

## 常见问题

### Q: 提示 "API token 或 project_id 未配置"

A: 检查 `.env` 文件是否配置了对应 Provider 的 API Key。

### Q: WebUI 发送消息后没有响应

A: 检查后端是否正常运行，查看控制台日志是否有错误输出。

### Q: Skill 没有被加载

A: 检查 `skills/` 目录下是否有完整的 `SKILL.md` 文件，且 YAML frontmatter 格式正确。

## 许可证

MIT

## 参考

- [agentskills.io 规范](https://agentskills.io/specification)
- [Kimi API 文档](https://platform.moonshot.cn/docs)
- [Qwen API 文档](https://help.aliyun.com/zh/dashscope/)
- [DeepSeek API 文档](https://platform.deepseek.com/api-docs/)
```

## 如果需要更简洁的版本

```markdown
# Mini Agent

轻量级 AI Agent 框架，遵循 agentskills.io 标准。

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 配置 API Key
cp .env.example .env
# 编辑 .env 填入你的 API Key

# 启动 CLI 交互模式
python main.py cli -i

# 启动 WebUI
python main.py webui
```

## 功能

- 🔧 4 个内置工具：read / write / bash / activate_skill
- 🧠 三种记忆模式：无记忆 / 有限记忆 / 永久记忆
- 🌊 流式输出，逐字显示
- 📦 Skills 即插即用
- 🔀 支持 Kimi / Qwen / DeepSeek

## 目录结构

```
core/          # 核心模块
skills/        # Skills 目录
adapters/      # CLI / WebUI
webui/         # 前端页面
```

## 命令

| 命令 | 说明 |
|------|------|
| `python main.py cli -i` | 交互式 CLI |
| `python main.py webui` | 启动 WebUI |
| `python main.py setup` | 初始化示例数据库 |

## 许可证

MIT