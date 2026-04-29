# 极简版的 Agent 项目 — 第一课:从0开始构建一个agent智能体项目,参考openClaw

## 第二篇章 Task文档

实现一个极简的 Python 版 agent runtime，用于学习 agent loop 与 skills 机制，遵守 [agentskills.io](https://agentskills.io) 开放标准。请先通读全文，再自行排序实施。

**优先级**：正确性 > 极简 > 优雅 > 功能。任何时候如果为了加功能要牺牲极简性，先github上拉一个支线任务。

---

## 1. 项目背景

- **用户身份**：PM，熟悉产品设计和工程概念，Python 初中级水平
- **学习目标**：理解 agent loop、tool use、skills 即插即用机制
- **实用目标**：后续要接入企业场景（医院住院指标查询、招标采购、发票解析等），每个场景一个 skill
- **最终交付形态**：MVP 可以本地跑通，未来可扩展接入微信 ClawBot

---≠≠≠≠

## 2. 核心设计原则（不可妥协）

1. **工具少而精**：内置工具只有 4 个（read / write / bash / activate_skill）
2. **Skills 即插即用**：文件系统发现，放入 `skills/` 目录 → 重启 → 生效
3. **系统提示短**：核心 system prompt < 1000 tokens，skill body 按需加载
4. **无状态 agent loop**：每次请求独立，不做会话持久化
5. **单一职责**：核心引擎只管 LLM 调度 + 工具执行 + skill 加载，所有业务能力（DB、OCR、HTTP）下沉到 skill 层
6. **agentskills.io 标准**：严格遵守 SKILL.md 的 YAML frontmatter 规范

---

## 3. 技术选型（已确认，不要擅自更改）

| 维度 | 决策 |
|------|------|
| 语言 | Python 3.10+ |
| LLM SDK | `openai` (三家厂商都兼容 OpenAI 协议) |
| 支持的 LLM | Kimi / Qwen / DeepSeek，运行时可切换 |
| 默认 LLM | Kimi (kimi-k2.5，多模态) |
| Web 框架 | FastAPI |
| 前端 | 单文件 HTML + Tailwind CDN + 原生 JS（**不引入任何前端构建工具**） |
| 配置 | `.env` (密钥) + `config.yaml` (结构化配置) |
| 日志 | Python stdlib `logging`，文件 + stdout |
| 异步 | **不做**。全部同步顺序执行 |
| 数据库 | **不做内置工具**。通过 skill 里的 Python 脚本 + bash 调用 |

---

## 4. 最终目录结构

```
mini-agent/
├── core/
│   ├── __init__.py
│   ├── agent.py              # Agent 主循环
│   ├── llm.py                # LLM 抽象(Kimi/Qwen/DeepSeek)
│   ├── skills.py             # Skill 扫描 + 加载
│   └── tools.py              # 工具注册表
│
├── tools_builtin/
│   ├── __init__.py
│   ├── file_ops.py           # read, write
│   ├── shell.py              # bash
│   └── skill_ops.py          # activate_skill
│
├── skills/                   # ⭐ 可插拔 skills 目录
│   ├── hello-world/          # 验证 skill 机制
│   │   ├── SKILL.md
│   │   └── scripts/
│   │       └── hello.py
│   └── sqlite-sample/        # 验证 DB-as-skill 模式
│       ├── SKILL.md
│       ├── scripts/
│       │   └── query.py
│       └── references/
│           └── schema.md
│
├── adapters/
│   ├── __init__.py
│   ├── cli.py                # 命令行入口
│   └── server.py             # FastAPI(WebUI + 预留 ClawBot HTTP)
│
├── webui/
│   └── index.html            # 单文件 UI
│
├── uploads/                  # 运行时上传文件目录(.gitignore 掉内容)
├── logs/                     # 日志目录(.gitignore 掉内容)
├── data/
│   └── sample.db             # 示例 SQLite
│
├── .env.example              # 密钥模板
├── .gitignore
├── config.yaml               # 主配置
├── requirements.txt
├── README.md                 # 用户文档
└── main.py                   # 统一入口:python main.py cli/webui
```

---

## 5. 模块接口契约

### 5.1 `core/llm.py`

```python
# 职责:封装三家 OpenAI-compatible 厂商,对外暴露统一接口

from typing import Literal, Optional
from openai import OpenAI

ProviderName = Literal["kimi", "qwen", "deepseek"]

PROVIDERS = {
    "kimi": {
        "base_url": "https://api.moonshot.cn/v1",
        "default_model": "kimi-k2.5",
        "supports_vision": True,
        "env_key": "MOONSHOT_API_KEY",
    },
    "qwen": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "default_model": "qwen-vl-max",
        "supports_vision": True,
        "env_key": "DASHSCOPE_API_KEY",
    },
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "default_model": "deepseek-chat",
        "supports_vision": False,
        "env_key": "DEEPSEEK_API_KEY",
    },
}

class LLM:
    def __init__(self, provider: ProviderName, api_key: str, model: Optional[str] = None):
        """根据 provider 名字初始化 OpenAI 客户端"""

    @property
    def supports_vision(self) -> bool: ...

    def complete(self, system: str, messages: list, tools: list) -> "LLMResponse":
        """
        调用 chat.completions.create
        返回结构化的 message(含 .content 和 .tool_calls)
        """
```

**注意事项**：
- 如果 provider 是 deepseek 且消息里有图片 → 日志警告，把图片路径当文本传
- tools 参数格式严格按 OpenAI function calling 规范

### 5.2 `core/skills.py`

```python
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
import yaml

@dataclass
class SkillMeta:
    name: str
    description: str
    path: Path
    # 可选字段: license, compatibility, metadata(dict)

class SkillLoader:
    def __init__(self, skills_dir: Path, enabled: Optional[list[str]] = None):
        """
        skills_dir: skills/ 目录
        enabled: 启用的 skill 名字列表(None 表示全部启用)
        """
        self.skills_dir = skills_dir
        self.enabled = enabled
        self.catalog: dict[str, SkillMeta] = {}

    def scan(self) -> None:
        """
        扫描目录,每个子目录如果有 SKILL.md 就读 frontmatter。
        遵守 agentskills.io 规范验证:
        - name 必填,只能小写字母/数字/连字符,<=64 字符
        - description 必填,<=1024 字符,不含尖括号
        """

    def get_catalog_text(self) -> str:
        """
        返回给 LLM 的目录说明(轻量元数据)。
        格式示例:
          Available skills (use activate_skill to load details):
          - hello-world: Greet the user...
          - sqlite-sample: Query a sample SQLite database...
        """

    def load_body(self, name: str) -> str:
        """
        读取指定 skill 的 SKILL.md,去掉 frontmatter 返回正文。
        找不到抛 KeyError。
        """
```

### 5.3 `core/tools.py`

```python
from typing import Callable

class ToolRegistry:
    def __init__(self):
        self.tools: dict[str, dict] = {}  # name -> {schema, handler}

    def register(self, name: str, description: str, parameters: dict, handler: Callable):
        """注册一个工具"""

    def get_openai_schemas(self) -> list[dict]:
        """返回 OpenAI function calling 格式的 tools 列表"""

    def execute(self, name: str, arguments: dict) -> str:
        """
        执行工具。
        - 不存在的工具返回错误字符串(而不是抛异常,让 LLM 自己纠错)
        - 所有返回值都转成字符串
        """
```

### 5.4 `core/agent.py`

```python
from pathlib import Path
from typing import Optional

class Agent:
    def __init__(
        self,
        llm: "LLM",
        skill_loader: "SkillLoader",
        tool_registry: "ToolRegistry",
        max_iterations: int = 15,
    ):
        ...

    def run(
        self,
        user_text: str,
        image_paths: Optional[list[str]] = None,
        on_step: Optional[Callable] = None,  # 每轮 loop 的回调,WebUI 用
    ) -> str:
        """
        执行一次完整的 agent loop。
        无状态,每次调用独立。

        流程:
        1. 构造 user message(含图片)
        2. 循环:
           a. 调 llm.complete(system, messages, tools)
           b. 如果 response 有 tool_calls:
              - 每个 tool_call 执行 tool_registry.execute(...)
              - 结果 append 到 messages
              - continue
           c. 否则: 返回 response.content
        3. 超过 max_iterations 返回错误提示
        """

    def _build_system_prompt(self) -> str:
        """
        核心 system prompt 结构:
        ----
        You are a task execution agent that uses tools and skills to help users.

        You have 4 built-in tools: read, write, bash, activate_skill.

        IMPORTANT: Before executing any specialized task, check if there's a 
        relevant skill in the catalog below. If yes, use activate_skill(name) 
        to load its full instructions. Don't guess — skills contain the exact 
        commands and schemas you need.

        {skill_catalog}

        Rules:
        - Always use activate_skill BEFORE bash-ing into a skill's scripts
        - After activating a skill, follow its SKILL.md instructions exactly
        - Keep responses concise unless user asks for detail
        ----
        """
```

---

## 6. 内置工具规范

### 6.1 `read`

```json
{
  "name": "read",
  "description": "Read the content of a text file. Returns up to 10,000 characters.",
  "parameters": {
    "type": "object",
    "properties": {
      "path": {"type": "string", "description": "File path (relative or absolute)"}
    },
    "required": ["path"]
  }
}
```

实现：读文件，超过 10000 字符截断并提示。二进制文件返回错误。

### 6.2 `write`

```json
{
  "name": "write",
  "description": "Write text content to a file. Creates parent directories if needed. Overwrites existing file.",
  "parameters": {
    "type": "object",
    "properties": {
      "path": {"type": "string"},
      "content": {"type": "string"}
    },
    "required": ["path", "content"]
  }
}
```

**安全限制**：`write` 只能写入 `workspace/`、`uploads/`、`logs/` 三个目录，不能往项目源码写。

### 6.3 `bash`

```json
{
  "name": "bash",
  "description": "Execute a shell command. Use this to run skill scripts, curl APIs, install packages, or any command-line operation. Returns stdout+stderr, truncated to 10,000 chars.",
  "parameters": {
    "type": "object",
    "properties": {
      "command": {"type": "string"},
      "timeout": {"type": "integer", "default": 60, "description": "Seconds"}
    },
    "required": ["command"]
  }
}
```

实现：
- `subprocess.run(command, shell=True, capture_output=True, timeout=...)`
- 返回格式：`[exit_code=N]\nSTDOUT:\n...\nSTDERR:\n...`
- 超时返回错误字符串
- **MVP 不做命令白名单**，但日志必须记录每次调用

### 6.4 `activate_skill`

```json
{
  "name": "activate_skill",
  "description": "Load the full instructions of a specific skill. Use this BEFORE running any skill-related command. The returned text is the skill's complete SKILL.md body.",
  "parameters": {
    "type": "object",
    "properties": {
      "name": {"type": "string", "description": "Exact skill name from the catalog"}
    },
    "required": ["name"]
  }
}
```

实现：调 `skill_loader.load_body(name)`，返回正文。找不到返回 `"Error: skill '{name}' not found. Available: ..."`。

---

## 7. 示例 Skills（必须包含）

### 7.1 `skills/hello-world/SKILL.md`

```markdown
---
name: hello-world
description: Greet the user by name and demonstrate the skill activation mechanism. Use when the user says hello, hi, 你好, or explicitly asks to test the skill system.
---

# Hello World Skill

This skill exists to verify that skill activation and bash execution work correctly.

## How to use

1. Extract the user's name from their message (default to "朋友" if not given).
2. Run the greeting script:

       bash: python skills/hello-world/scripts/hello.py "<name>"

3. Return the script's output to the user.

## Example

User: "你好,我叫席朋飞"
Action: `python skills/hello-world/scripts/hello.py "席朋飞"`
Output: `你好,席朋飞!Mini Agent 已经正常运作。`
Response to user: 你好,席朋飞!Mini Agent 已经正常运作。
```

`scripts/hello.py`：

```python
#!/usr/bin/env python3
import sys
name = sys.argv[1] if len(sys.argv) > 1 else "朋友"
print(f"你好,{name}!Mini Agent 已经正常运作。")
```

### 7.2 `skills/sqlite-sample/SKILL.md`

包含一个示例 SQLite 数据库查询场景。数据库用 `data/sample.db`，包含一张 `employees` 表（id, name, department, salary, hire_date），预填 10 条示例数据。

`SKILL.md` 要包含：
- 表结构说明（或者引用 `references/schema.md`）
- 怎么通过 bash 调用 `scripts/query.py`
- 查询示例（按部门统计平均工资、查找特定员工等）
- 只允许 SELECT 的安全说明

`scripts/query.py` 实现：
- 接受 `--sql "SELECT ..."` 参数
- 启动时验证 SQL 以 `select` 开头
- 执行查询，结果以 JSON 输出
- 默认 LIMIT 100

提供一个 `data/seed_sample_db.py` 脚本，用来生成 `sample.db`（第一次运行时由 main.py 检测并调用）。

---

## 8. WebUI 规范

### 8.1 视觉要求

- 极简但不丑陋
- Tailwind CSS（CDN），参考 Vercel / Linear / Anthropic 官网的"克制的现代感"
- 配色：浅色主题，使用中性灰 + 一个强调色（建议 indigo-600 或 neutral）
- 字体：系统字体栈（`-apple-system, ...`）
- 不要使用表情包、花哨动画、渐变色、阴影堆叠

### 8.2 布局

```
┌────────────────────────────────────────────────────┐
│ Mini Agent                      [Model: Kimi ▾]    │  ← 顶部栏
├────────────────────────────────────────────────────┤
│                                                     │
│  [对话/事件流区域,可滚动]                           │
│                                                     │
│  ┌─ User ────────────────────────┐                 │
│  │ 解析这张发票                   │                 │
│  │ [🖼 invoice.jpg]               │                 │
│  └───────────────────────────────┘                 │
│                                                     │
│  ┌─ Agent ───────────────────────┐                 │
│  │ 🔧 activate_skill(parse-      │                 │
│  │    invoice)                   │                 │
│  │ 🔧 bash: python ...           │                 │
│  │ ✓ 已识别,发票号:INV-001       │                 │
│  └───────────────────────────────┘                 │
│                                                     │
├────────────────────────────────────────────────────┤
│  [📎]  [ 输入内容...            ]  [  发送  ]      │  ← 底部输入区
└────────────────────────────────────────────────────┘
```

### 8.3 功能

- **文字输入**：多行 textarea，Enter 发送，Shift+Enter 换行
- **文件上传**：
  - 点击 📎 按钮选文件
  - 支持拖拽到输入区
  - 支持多个文件
  - 上传的图片/文件先 POST 到 `/api/upload`，返回路径后在发消息时带上
- **模型切换**：右上角下拉，切换立即生效（前端在 localStorage 记住选择）
- **对话流展示**：
  - 用户消息：右对齐的气泡
  - Agent 响应：左对齐
  - 工具调用：用 `🔧 tool_name(args_summary)` 的紧凑行展示，默认折叠参数详情，点击展开
  - 错误：红色文字

### 8.4 后端接口

**MVP 先不做流式，用简单的一次性返回：**

```
POST /api/chat
Body:
{
  "text": "用户消息",
  "image_paths": ["/uploads/xxx.jpg"],
  "provider": "kimi"
}
Response:
{
  "reply": "最终文本回复",
  "steps": [
    {"type": "tool_call", "name": "activate_skill", "args": {...}, "result": "..."},
    {"type": "tool_call", "name": "bash", "args": {...}, "result": "..."}
  ]
}

POST /api/upload
Body: multipart/form-data
Response: {"path": "/uploads/xxx.jpg"}

GET /api/providers
Response: [{"name": "kimi", "supports_vision": true, "configured": true}, ...]
  configured 表示对应的 env key 是否存在
```

**后期升级**（本次不做）：把 `/api/chat` 改成 SSE 流式，前端逐步显示工具调用过程。

---

## 9. 配置文件

### 9.1 `.env.example`

```
# 至少填一个,对应 config.yaml 里 active_provider
MOONSHOT_API_KEY=
DASHSCOPE_API_KEY=
DEEPSEEK_API_KEY=
```

### 9.2 `config.yaml`

```yaml
# 当前启用的 LLM
active_provider: kimi

# Provider 的 model 覆盖(不填就用默认)
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
  enabled: null  # null = 全部启用,或者填白名单数组

# Agent 配置
agent:
  max_iterations: 15

# WebUI 配置
webui:
  host: 127.0.0.1
  port: 8000
```

### 9.3 `requirements.txt`

```
openai>=1.50.0
pyyaml>=6.0
python-dotenv>=1.0.0
pydantic>=2.0
fastapi>=0.110.0
uvicorn[standard]>=0.27.0
python-multipart>=0.0.9
rich>=13.0.0
```

---

## 10. 统一入口 `main.py`

```python
# 支持的子命令:
#   python main.py cli "消息内容"                  # 单次执行并退出
#   python main.py cli --interactive               # 交互式 REPL
#   python main.py webui                           # 启动 WebUI(默认)
#   python main.py setup                           # 初始化示例数据(sample.db)
#
# 使用 argparse,清晰的 help 输出
```

---

## 11. 日志规范

- 位置：`logs/agent-YYYY-MM-DD.log`
- 格式：`[时间] [级别] [模块] 内容`
- 级别：
  - INFO：每次请求收到、每轮 LLM 调用、每次工具执行
  - DEBUG：完整的 messages 和 tool_calls payload
  - ERROR：异常栈
- 同时输出到 stdout（彩色，用 `rich`）和文件（纯文本）

---

## 12. 错误处理哲学

- **工具执行失败** → 返回错误字符串给 LLM（"[error] XXX"），让 LLM 自己决定重试还是换路
- **LLM 调用失败**（网络/鉴权）→ 立即抛异常给调用方，不在 loop 里重试
- **Skill 不存在** → `activate_skill` 返回错误字符串 + 可用列表
- **超过 max_iterations** → 返回 `"任务未能在 15 轮内完成,已中止。最后的进展是:..."`

---

## 13. 实施路线（建议顺序，你可以调整）

### Phase 1 — 核心可跑（CLI）

目标：命令行能跑完一个 hello-world 测试。

1. 建目录 + `requirements.txt` + `.env.example` + `.gitignore`
2. `core/llm.py`（先只实 Kimi，结构预留多 provider）
3. `core/tools.py`
4. `core/skills.py`
5. `tools_builtin/*.py`（4 个工具）
6. `core/agent.py`
7. `skills/hello-world/`
8. `adapters/cli.py`
9. `main.py cli` 入口
10. **验收**：`python main.py cli "你好,我叫小明"` → 返回 hello-world skill 的问候

### Phase 2 — 多 LLM + 数据库 skill

1. `core/llm.py` 补齐 Qwen / DeepSeek
2. `skills/sqlite-sample/` + `data/seed_sample_db.py`
3. `python main.py setup` 自动建库
4. **验收**：`python main.py cli "查询薪资最高的3个员工"` → 正确调用 sqlite-sample skill

### Phase 3 — WebUI

1. `adapters/server.py`（FastAPI，三个接口）
2. `webui/index.html`
3. `main.py webui` 入口
4. **验收**：浏览器打开 `http://127.0.0.1:8000`
   - 文字消息能往返
   - 能上传图片
   - 能切换模型
   - 工具调用在 UI 里可见

### Phase 4（可选，本次可能不做）

- SSE 流式
- HTTP 端点适配 ClawBot
- 更多真实 skill

---

## 14. 验收清单（全部做完后自查）

- [ ] 目录结构完全符合第 4 节
- [ ] 四个内置工具都能正常工作
- [ ] hello-world skill 能被激活并执行
- [ ] sqlite-sample skill 能正确查库
- [ ] 三个 LLM 都能切换（至少 Kimi 必须 100% 可用）
- [ ] CLI 模式可用
- [ ] WebUI 模式可用，文件上传能用
- [ ] 所有工具调用都写进日志
- [ ] `README.md` 包含：5 分钟快速开始、如何加新 skill、目录说明
- [ ] 代码总行数（不含空行和注释）< 1000 行

---

## 15. 禁止事项

- ❌ 不要引入 langchain / llamaindex / agno 等 agent 框架
- ❌ 不要在核心里写死"数据库"、"OCR"、"HTTP" 等业务概念
- ❌ 不要做会话持久化（用 Redis、SQLite 存 history 等）
- ❌ 不要做并发（asyncio/threading/多进程）
- ❌ 不要做流式响应（MVP 本次）
- ❌ 不要引入前端构建工具（webpack/vite/npm 等）
- ❌ 不要做认证/登录（本地单机工具，不需要）
- ❌ 不要过度 OOP，简单函数能解决的别写类

---

## 16. 和我（用户）协作的节奏

- 每个 Phase 完成后停下来，让我手动验收
- 遇到设计上的分叉（两种都能走），列出选项问我，不要擅自决定
- 遇到技术卡点（比如 API 行为和预期不符），先查官方文档（可以 web search），再问我
- **代码注释用中文**，变量名和函数名用英文
- 提交前跑一遍基本冒烟测试

---

## 附录 A：agentskills.io SKILL.md 规范要点

- 文件名必须叫 `SKILL.md`（大小写敏感）
- YAML frontmatter 必含 `name` 和 `description`
- `name`：最多 64 字符，只能小写字母/数字/连字符，不能以连字符开头/结尾，不能有连续连字符
- `description`：最多 1024 字符，必须说明做什么和何时用，**不能含尖括号**（`<` 或 `>`）
- 可选字段：`license`、`compatibility`、`metadata`（dict）
- 官方 spec：https://agentskills.io/specification

## 附录 B：三家 LLM 的 API 速查

| | Kimi | Qwen | DeepSeek |
|---|---|---|---|
| base_url | https://api.moonshot.cn/v1 | https://dashscope.aliyuncs.com/compatible-mode/v1 | https://api.deepseek.com/v1 |
| 默认 model | kimi-k2.5 | qwen-vl-max | deepseek-chat |
| Vision | ✅ | ✅ | ❌ |
| Tool use | ✅ | ✅ | ✅ |
| SDK | openai | openai | openai |

图片传入方式（三家统一，OpenAI 格式）：

```python
{
  "role": "user",
  "content": [
    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64}"}},
    {"type": "text", "text": "描述这张图"}
  ]
}
```

---

**文档完**。准备好就开始 Phase 1。任何不清楚的地方先问，别猜。
