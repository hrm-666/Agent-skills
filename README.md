# Task 6 — 多人协同 Mini-Agent 仓库

这是一个用于课程作业的多人协同仓库。每位成员在根目录下维护自己的独立实现，互不覆盖、互不干扰。

当前仓库中主要包含以下成员目录：

- `bwz/`
- `lsj/`
- `mhr/`

## 仓库协作方式

- 每位成员在自己的目录中独立开发
- 各自维护自己的依赖、配置、技能和前后端入口
- 敏感信息放在个人目录下的 `.env` 中，不提交到 Git
- 运行产物如日志、缓存、上传文件、临时输出等通过根目录 `.gitignore` 统一忽略

如果你只负责自己的部分，通常只需要进入自己的目录进行开发和运行即可。

## `mhr/` 当前项目说明

`mhr/` 目录目前是一个可运行的极简 Mini-Agent 实现，支持：

- CLI 对话模式
- WebUI 聊天页面
- 基于 tool calling 的 Agent loop
- 技能加载机制
- 文件上传
- 多模型切换

当前已接入的模型提供方：

- `kimi`
- `qwen`
- `deepseek`

其中 `kimi` 和 `qwen` 支持视觉输入，`deepseek` 当前按文本模式使用。

## `mhr/` 目录结构

```text
mhr/
├── main.py                      # 项目入口，支持 cli / webui
├── config.yaml                  # 运行配置
├── requirements.txt             # Python 依赖
├── .env.example                 # 环境变量模板
├── Task6.md                     # 作业说明
├── TECHNICAL_WALKTHROUGH.md     # 当前实现的技术解读
│
├── adapters/                    # CLI / FastAPI 入口
├── core/                        # Agent、LLM、tools、skills 核心逻辑
├── tools_builtin/               # 内置工具：read / write / bash / activate_skill
├── skills/                      # 可扩展技能目录
├── webui/                       # 前端页面
├── uploads/                     # 上传文件目录
├── logs/                        # 运行日志目录
└── workspace/                   # 技能执行输出目录
```

## `mhr/` 已实现能力

### 1. 双入口运行

支持两种启动方式：

- 命令行模式
- Web 页面模式

### 2. 内置 4 个基础工具

- `read`
- `write`
- `bash`
- `activate_skill`

### 3. Skill 机制

Agent 会先读取技能目录摘要，在需要时再加载具体 `SKILL.md`，再按技能说明调用脚本。

当前 `mhr/skills/` 下包含：

- `hello-world`：机制示例 skill
- `pledgebox-order`：PledgeBox 订单获取与清洗 skill

### 4. PledgeBox 订单处理

`pledgebox-order` skill 用于：

- 从 PledgeBox OpenAPI 获取订单
- 调用当前选中的模型进行字段清洗
- 输出原始订单、清洗结果、错误日志和进度文件

默认输出目录：

```text
mhr/workspace/pledgebox-order-output/
```

## 快速开始

以下命令默认在 `mhr/` 目录下执行。

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env`，并至少填写一个与 `config.yaml` 中 `active_provider` 对应的 API Key。

当前环境变量模板为：

```env
MOONSHOT_API_KEY=
DASHSCOPE_API_KEY=
DEEPSEEK_API_KEY=
```

### 3. 检查配置

默认配置见 [mhr/config.yaml](./mhr/config.yaml)：

- 默认 provider：`kimi`
- 默认模型：
  - `kimi-k2.5`
  - `qwen-vl-max`
  - `deepseek-v4-flash`
- WebUI 默认地址：`127.0.0.1:8000`

## 运行方式

### CLI 单轮模式

```bash
python main.py cli "你好，帮我介绍一下当前可用技能"
```

### CLI 交互模式

```bash
python main.py cli --interactive
```

### 启动 WebUI

```bash
python main.py webui
```

如果不带参数直接运行：

```bash
python main.py
```

默认也会启动 WebUI。

## WebUI 接口概览

`mhr` 当前 Web 端基于 FastAPI，主要接口包括：

- `GET /`：返回页面
- `GET /api/providers`：返回可用模型列表与配置状态
- `POST /api/chat`：普通聊天请求
- `POST /api/chat/stream`：流式聊天请求
- `POST /api/upload`：上传文件
- `POST /api/tool/confirm`：确认高风险工具调用

## 相关说明

- `mhr/.env` 不应提交到仓库
- `mhr/logs/`、`mhr/uploads/`、`mhr/workspace/` 下的运行产物默认不建议提交
- `mhr/references/` 主要用于参考实现，不属于当前核心运行目录

## 参考文档

- [mhr/TECHNICAL_WALKTHROUGH.md](./mhr/TECHNICAL_WALKTHROUGH.md)
- [mhr/Task6.md](./mhr/Task6.md)
