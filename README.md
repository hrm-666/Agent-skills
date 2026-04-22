# Mini Agent

一个遵守 `agentskills.io` 思路的极简 Python Agent Runtime 练习项目。

项目目标是用尽可能少的抽象，跑通一条清晰的链路：

- `agent loop`
- `tool use`
- `skills 即插即用`
- `CLI + WebUI` 共用同一套运行时装配逻辑

当前已实现：

- 4 个内置工具：`read / write / bash / activate_skill`
- 3 个 provider：`kimi / qwen / deepseek`
- 2 个示例 skill：`hello-world / sqlite-sample`
- `CLI` 单次执行与交互式 `REPL`
- `WebUI` 文本对话、图片上传、provider 切换、工具步骤展示

## 5 分钟快速开始

1. 创建虚拟环境并安装依赖

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2. 配置 API Key

把 `.env.example` 复制为 `.env`，至少填写一个和 `config.yaml` 中 `active_provider` 对应的 key。

```env
MOONSHOT_API_KEY=your_key_here
DASHSCOPE_API_KEY=
DEEPSEEK_API_KEY=
```

3. 初始化示例数据库

```powershell
python main.py setup
```

4. 跑一次 CLI

```powershell
python main.py cli "你好，我叫小明"
```

5. 启动 WebUI

```powershell
python main.py
```

浏览器打开 `http://127.0.0.1:8000`。

## 环境准备与依赖安装

推荐环境：

- Python `3.10+`
- Windows PowerShell、macOS Terminal 或 Linux shell
- 至少一个可用的 OpenAI-compatible provider API Key

安装依赖：

```powershell
pip install -r requirements.txt
```

项目依赖包括：

- `openai`
- `pyyaml`
- `python-dotenv`
- `pydantic`
- `fastapi`
- `uvicorn`
- `python-multipart`
- `rich`

## `.env` 配置方式

项目使用：

- `.env` 保存 API Key
- `config.yaml` 保存结构化配置

`.env.example` 内容如下：

```env
MOONSHOT_API_KEY=
DASHSCOPE_API_KEY=
DEEPSEEK_API_KEY=
```

最少填写一个。默认 provider 由 [config.yaml](./config.yaml) 中的 `active_provider` 决定：

```yaml
active_provider: kimi
```

WebUI 首次加载时，如果浏览器里还没有保存过 provider 选择，也会优先使用这里的 `active_provider`。

如果你想临时切换 provider，也可以在 CLI 启动时传：

```powershell
python main.py cli --provider qwen "你好"
```

## 运行命令

### `python main.py setup`

初始化示例数据库 `data/sample.db`。

```powershell
python main.py setup
```

如果想强制重建数据库：

```powershell
python main.py setup --force
```

数据库中会创建一张 `employees` 表，并写入 10 条示例员工数据，供 `sqlite-sample` skill 使用。

### `python main.py cli`

单次执行：

```powershell
python main.py cli "查询薪资最高的3个员工"
```

交互式 REPL：

```powershell
python main.py cli --interactive
```

显示工具调用过程：

```powershell
python main.py cli --show-steps "你好，我叫小明"
```

CLI 的特点：

- 每次请求都是无状态的
- 模型会先看 skill catalog，再决定是否激活 skill
- 工具调用、LLM 调用和错误会写入 `logs/`

### `python main.py webui`

启动 WebUI：

```powershell
python main.py webui
```

直接运行：

```powershell
python main.py
```

上面两种方式等价；不带子命令时会默认启动 WebUI。

默认监听地址由 `config.yaml` 控制：

```yaml
webui:
  host: 127.0.0.1
  port: 8000
```

WebUI 当前支持：

- 文字输入
- 多文件上传
- 图片附件可直接参与视觉推理
- 普通文件附件会以路径文本形式附加给模型
- 切换 provider
- 展示工具调用步骤

WebUI 里的 provider 选择顺序如下：

1. 浏览器 `localStorage` 中已保存的 provider
2. `config.yaml` 中的 `active_provider`
3. 第一个已配置 API Key 的 provider
4. provider 列表中的第一个

## WebUI 接口约定

### `GET /api/providers`

返回 provider 数组：

```json
[
  {"name": "kimi", "supports_vision": true, "configured": true},
  {"name": "qwen", "supports_vision": true, "configured": false}
]
```

说明：

- 返回值是数组，不包 `providers` 外层对象
- 前端会根据返回结果渲染 provider 下拉

### `POST /api/upload`

单文件上传，返回上传后的相对 Web 路径：

```json
{"path": "/uploads/example.png"}
```

说明：

- 当前前端支持多文件，但会逐个调用 `/api/upload`
- 聊天时只接受 `uploads/` 目录内的附件路径

### `POST /api/chat`

请求体示例：

```json
{
  "text": "请结合附件帮我分析",
  "image_paths": ["/uploads/example.png", "/uploads/report.pdf"],
  "provider": "kimi"
}
```

返回体示例：

```json
{
  "reply": "最终文本回复",
  "steps": [
    {"type": "tool_call", "name": "activate_skill", "args": {"name": "sqlite-sample"}, "result": "..."}
  ]
}
```

说明：

- `provider` 只允许 `kimi / qwen / deepseek`
- 图片附件在支持视觉的 provider 下会转成 `image_url`
- 非图片附件会作为附件路径文本附加给模型

## 如何新增一个 skill

项目当前只扫描 `./skills/` 目录下的一级子目录。新增一个 skill 的最小步骤如下：

1. 创建目录 `skills/<skill-name>/`
2. 在目录里创建 `SKILL.md`
3. 写合法的 YAML frontmatter
4. 按需添加 `scripts/`、`references/`、`assets/`
5. 重启 CLI 或 WebUI

最小示例：

```markdown
---
name: my-skill
description: Do something specific and say when to use it.
---

# My Skill

1. Explain what the agent should do.
2. If needed, run:

       python skills/my-skill/scripts/run.py
```

需要注意的约束：

- 目录名必须和 `name` 一致
- `name` 只能包含小写字母、数字和连字符
- `description` 必须是非空字符串，且不能包含尖括号
- 项目当前遵循“元数据先扫描，正文按需激活”的加载方式

已有示例可参考：

- [skills/hello-world/SKILL.md](./skills/hello-world/SKILL.md)
- [skills/sqlite-sample/SKILL.md](./skills/sqlite-sample/SKILL.md)

## 目录结构说明

```text
.
├── adapters/              # CLI / FastAPI 适配层
├── core/                  # Agent、LLM、SkillLoader、ToolRegistry
├── data/                  # 示例数据库与初始化脚本
├── logs/                  # 运行日志
├── skills/                # 本地可插拔 skills
├── tools_builtin/         # 4 个内置工具实现
├── uploads/               # WebUI 上传文件落盘目录
├── webui/                 # 单文件前端页面
├── workspace/             # write 工具允许写入的目录之一
├── config.yaml            # 主配置
├── main.py                # 统一入口
└── requirements.txt       # Python 依赖
```

各目录职责：

- `core/`：核心运行时，不承载具体业务能力
- `tools_builtin/`：内置工具定义与 handler
- `skills/`：业务能力下沉位置，数据库、脚本、参考资料都放这里
- `adapters/`：把核心运行时接到 CLI 和 WebUI
- `uploads/ / logs/ / workspace/`：运行期目录，不写入项目源码逻辑

## 当前内置工具

- `read`：读取文本文件，超长截断
- `write`：只允许写到 `workspace/`、`uploads/`、`logs/`
- `bash`：执行 shell 命令并回传统一格式输出
- `activate_skill`：按名字加载指定 skill 的 `SKILL.md` 正文

## 示例 skills

### `hello-world`

用于验证 skill 激活与脚本执行链路是否正常。适合测试“你好”“hello”这类请求。

### `sqlite-sample`

用于查询 `data/sample.db` 中的员工示例数据。适合测试：

- 查询高薪员工
- 按部门统计平均工资
- 查找某个员工信息

## 日志与运行产物

- 日志路径：`logs/agent-YYYY-MM-DD.log`
- 上传文件目录：`uploads/`
- 示例数据库：`data/sample.db`

`write` 工具默认不能写项目源码，只能写入：

- `workspace/`
- `uploads/`
- `logs/`

## 统一启动流程

无论是 CLI 还是 WebUI，都会复用下面这条 bootstrap 顺序：

1. 加载 `.env`
2. 读取 `config.yaml`
3. 初始化日志
4. 初始化 `SkillLoader` 并扫描 `skills/`
5. 初始化 `ToolRegistry` 并注册内置工具
6. 创建当前 provider 的 `LLM`
7. 创建 `Agent`

## 已知限制

- 当前仍是无状态 agent runtime，不做会话持久化。
- WebUI 采用一次性请求响应，未实现 SSE 流式输出。
- skill 扫描范围目前只覆盖项目内的 `./skills/`。
- `write` 工具只允许写入 `workspace/`、`uploads/`、`logs/`。
- 不同 provider 的 tool-use 稳定性依赖具体模型版本，跨厂商行为可能不完全一致。
- 当前代码规模已经超过原始任务里提出的 `<1000` 行目标，后续若继续扩展，建议拆分与收敛模块边界。

## 后续可扩展点

- 为 `/api/chat` 增加 SSE 流式返回。
- 扩展 skill 扫描范围到 `.agents/skills/` 或用户级目录。
- 增加更多真实业务 skill，例如 OCR、发票解析、指标查询。
- 增强 skill 兼容解析与 `allowed-tools` 执行约束。
- 为 WebUI 增加更系统的运行状态、错误诊断和历史回放能力。
- 对代码进行进一步拆分与精简，向最初的极简目标回收复杂度。

## 参考文档

- [Task6.md](./Task6.md)
- 补充资料已集中放在 `extra_materials/`，不属于运行主结构
- `extra_materials/` 中保留了实现步骤、阶段汇报、修复清单和 `agentskills-main/` 参考资料
