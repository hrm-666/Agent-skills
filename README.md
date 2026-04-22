# Mini Agent

基于大语言模型的智能代理系统，支持多种 LLM Provider（Kimi、Zai、Deepseek），内置工具系统和可扩展的技能系统。

## 功能特性

- **多 LLM Provider 支持**：Kimi（Moonshot）、Zai（智谱 GLM）、Deepseek
- **内置工具**：文件读写、bash命令、技能激活
- **技能系统**：可扩展的技能目录，支持 agentskills.io 规范
- **多种交互模式**：CLI 命令行、WebUI 界面
- **日志系统**：双输出（文件 + 控制台彩色输出）

## 目录结构

```
mini-agent/
├── main.py                 # 统一入口
├── config.yaml             # 配置文件
├── requirements.txt       # Python 依赖
├── core/                  # 核心模块
│   ├── agent.py           # Agent 主循环
│   ├── llm.py             # LLM 调用封装
│   ├── tools.py           # 工具注册与执行
│   ├── skills.py          # 技能加载器
│   ├── logging_config.py  # 日志配置
│   └── utils.py           # 工具函数
├── adapters/              # 适配器
│   ├── cli.py             # CLI 模式
│   └── server.py          # FastAPI WebUI 服务器
├── tools_builtin/         # 内置工具
│   ├── bash.py            # Shell 命令执行
│   ├── read.py           # 文件读取
│   ├── write.py          # 文件写入
│   └── skill_ops.py       # 技能激活
├── skills/                # 技能目录
│   ├── hello-world/       # 示例技能
│   └── sqlite-sample/     # 数据库查询技能
├── webui/                 # WebUI 前端
│   └── index.html         # 单页应用
└── uploads/              # 文件上传目录
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置 API Key

在项目根目录创建 `.env` 文件：

```env
MOONSHOT_API_KEY="your-kimi-api-key"
ZAI_API_KEY="your-zai-api-key"
DEEPSEEK_API_KEY="your-deepseek-api-key"
```

### 3. 初始化示例数据库（可选）

```bash
python main.py setup
```

### 4. 运行

**CLI 模式**：

```bash
python main.py cli "你好，请介绍一下自己"
```

**WebUI 模式**：

```bash
python main.py webui
```

然后在浏览器打开 http://127.0.0.1:8000

## 配置说明

配置文件 `config.yaml`：

```yaml
# 当前启用的 LLM Provider
active_provider: deepseek

# Provider 的 model 覆盖
providers:
  kimi:
    model: kimi-k2.5
  zai:
    model: glm-4.7
  deepseek:
    model: deepseek-chat

# 技能配置
skills:
  dir: ./skills
  enabled: null  # null 表示全部启用

# Agent 配置
agent:
  max_iterations: 15

# WebUI 配置
webui:
  host: 127.0.0.1
  port: 8000

# 日志配置
logging:
  dir: ./logs
  level: INFO
  console: true
  file: true
```

## 内置工具

| 工具 | 说明 |
|------|------|
| `read` | 读取文本文件内容（最多 10,000 字符） |
| `write` | 写入文本到文件（仅限 workspace/uploads/logs 目录） |
| `bash` | 执行 Shell 命令（默认超时 60 秒） |
| `activate_skill` | 加载技能完整说明 |

## 技能系统

技能目录位于 `./skills`，每个技能是一个子目录，包含 `SKILL.md` 文件。

### 内置技能

- **hello-world**：演示技能激活机制
- **sqlite-sample**：查询示例 SQLite 数据库

### 开发新技能

1. 在 `skills/` 下创建子目录
2. 编写 `SKILL.md`，包含 frontmatter 和技能说明

```markdown
---
name: my-skill
description: 技能描述（最多 1024 字符）
---

# My Skill

技能使用说明...
```

## 命令行参数

### CLI 模式

```bash
python main.py cli "消息内容" [--provider kimi|zai|deepseek]
```

### WebUI 模式

```bash
python main.py webui
```

### 初始化数据库

```bash
python main.py setup
```
