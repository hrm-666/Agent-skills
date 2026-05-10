# Mini Agent

一个极简的 Python Agent 框架，遵循 [agentskills.io](https://agentskills.io) 开放标准。支持流式输出、会话历史、工具安全策略、操作确认机制。

目前该项目实现了访问api接口并保存数据功能，尚未添加清洗逻辑

## 5 分钟快速开始

### 1. 环境准备

```bash
# 创建虚拟环境
python -m venv .venv

# 激活虚拟环境（Windows）
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置 API Key

```bash
cp .env.example .env
```

编辑 `.env`，至少填入一个 provider 的密钥：

```ini
MOONSHOT_API_KEY=你的Kimi密钥
DEEPSEEK_API_KEY=你的DeepSeek密钥
DASHSCOPE_API_KEY=你的通义千问密钥
```

### 3. 初始化示例数据库（可选）

```bash
python main.py setup
```

### 4. 运行

```bash
# 单次执行
python main.py cli "你好，我叫小明"

# 交互模式
python main.py cli --interactive

# WebUI（浏览器打开 http://127.0.0.1:8000）
python main.py webui
```

### 5. 测试 Skill

```bash
python main.py cli "你好"
python main.py cli "查询薪资最高的3个员工"
python main.py cli "帮我从这个API文档里提取GET接口数据：API-CN.pdf"
```

---

## 目录结构

```
mini-agent/
├── core/                    # 核心引擎
│   ├── agent.py            # Agent 主循环（支持流式、确认暂停）
│   ├── llm.py              # LLM 抽象（Kimi / Qwen / DeepSeek，含流式）
│   ├── skills.py           # Skill 扫描与加载
│   ├── tools.py            # 工具注册表 + ToolPolicy 安全策略
│   └── logging_setup.py    # 日志（Rich 彩色 + 文件双输出）
│
├── tools_builtin/           # 内置工具
│   ├── file_ops.py         # read / write（write 仅限 workspace/）
│   ├── shell.py            # bash（返回结构化 dict）
│   └── skill_ops.py        # activate_skill
│
├── skills/                  # 可插拔 Skills
│   ├── hello-world/        # 打招呼示例
│   ├── sqlite-sample/      # SQLite 数据库查询
│   └── api-extractor/      # API 文档 GET 接口提取
│
├── adapters/                # 入口适配器
│   ├── cli.py              # CLI（Rich 格式化）
│   └── server.py           # WebUI（SSE 流式、会话历史、确认机制）
│
├── webui/                   # 前端
│   └── index.html          # 支持流式显示、文件上传、确认弹窗
│
├── data/                    # 数据文件
├── logs/                    # 日志（自动生成，按天轮转）
├── uploads/                 # 用户上传
├── workspace/               # Agent 输出目录
│
├── config.yaml              # 配置文件
├── main.py                  # 入口
└── requirements.txt         # 依赖
```

---

## 配置文件

```yaml
# 当前使用的模型
active_provider: deepseek

# 各 provider 的模型覆盖
providers:
  kimi:
    model: kimi-k2.5
  qwen:
    model: qwen-vl-max
  deepseek:
    model: deepseek-chat

# Skill 配置
skills:
  dir: ./skills
  enabled: null          # null = 全部启用

# 工作区
workspace:
  dir: ./workspace

# Agent 配置
agent:
  max_iterations: 15

# WebUI
webui:
  host: 127.0.0.1
  port: 8000

# 工具安全策略
tool_policy:
  default: allow         # 默认放行
  bash:
    blocked_patterns:    # 直接拦截的高危命令
      - "rm -rf /"
      - "sudo"
      - "shutdown"
      - "reboot"
      - "mkfs"
    confirm_patterns:    # 需用户确认的命令
      - "rm "
      - "mv "
      - "chmod "
      - "chown "
  write:
    confirm_paths:       # 写入需确认的敏感文件
      - ".env"
      - "config.yaml"
```

---

## Web API

| 端点 | 说明 |
|---|---|
| `POST /api/chat` | 普通对话 |
| `POST /api/chat/stream` | SSE 流式对话（逐字输出 + 工具步骤实时推送） |
| `POST /api/tool/confirm` | 确认待审批的工具操作 |
| `POST /api/upload` | 上传文件 |
| `GET /download/{path}` | 下载 workspace 内的文件 |
| `POST /api/session/reset` | 重置会话历史 |
| `GET /api/providers` | 查询可用的 LLM |

---

## 内置 Skills

### api-extractor（API 文档 GET 接口提取）

从 PDF / Markdown / TXT 格式的 API 文档中提取 GET 接口，自动拼接参数并发起请求，将 JSON 响应整理为 CSV / Markdown / JSON。

```
python skills/api-extractor/scripts/run.py --doc "文档路径" --dry-run
python skills/api-extractor/scripts/run.py --doc "文档路径" --format csv
```

处理流程：
1. 提取文本（pypdf 或直接读取）
2. 定位 GET 接口块，解析参数表与响应字段表
3. 拼接完整 request_url，执行 GET 请求
4. 展平 JSON 数据为结构化记录
5. 导出 CSV / Markdown / JSON

### sqlite-sample（SQLite 数据库查询）

查询示例员工数据库。

### hello-world（问候）

验证 Skill 激活机制是否正常。

---

## 如何添加新 Skill

1. 在 `skills/` 下创建目录（小写字母 + 连字符）
2. 编写 `SKILL.md`（含 YAML frontmatter，name + description 必填）
3. 如需脚本，放入 `scripts/` 目录
4. 重启 Agent 即自动扫描加载

```
skills/your-skill/
├── SKILL.md
└── scripts/
    └── your_script.py
```

SKILL.md 模板：

```markdown
---
name: your-skill
description: 一句话说明这个技能的使用场景（≤1024 字符，不含尖括号）
---

# Your Skill

## 使用方法

    python skills/your-skill/scripts/your_script.py --arg value
```

### Skill 规范

| 规则 | 要求 |
|---|---|
| 文件名 | 必须为 `SKILL.md` |
| `name` | 小写字母/数字/连字符，≤64 字符 |
| `description` | ≤1024 字符，不含 `<` `>` |
| 可选字段 | license, compatibility, metadata |
