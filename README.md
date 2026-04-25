# Mini Agent

一个遵循 [agentskills.io](https://agentskills.io) 开放标准的轻量级 AI Agent 框架。

## 功能特性

- 🔧 **极简工具集**：内置 read / write / bash / activate_skill 四个核心工具
- 📦 **即插即用 Skills**：放入 `skills/` 目录即可自动发现和加载
- 🧠 **多 LLM 支持**：兼容 Kimi、Qwen、DeepSeek，运行时随时切换
- 💻 **命令行 + WebUI**：支持终端交互和浏览器界面两种使用方式
- 📝 **完整日志**：自动记录到 `logs/` 目录，便于调试

## 快速开始

### 环境要求

- Python 3.10 或更高版本

### 安装步骤

1. 克隆项目

```bash
git clone https://github.com/alangao22/agent_gzh.git
cd agent_gzh
```

2. 创建虚拟环境（推荐）

```bash
python -m venv venv
source venv/bin/activate      # Linux/Mac
venv\Scripts\activate         # Windows
```

3. 安装依赖

```bash
pip install -r requirements.txt
```

4. 配置 API Key

复制 `.env.example` 为 `.env`，填入对应厂商的 API Key：

```env
MOONSHOT_API_KEY=your_kimi_api_key
DASHSCOPE_API_KEY=your_qwen_api_key
DEEPSEEK_API_KEY=your_deepseek_api_key
```

5. 初始化示例数据库

```bash
python main.py setup
```

### 运行

**命令行交互模式**

```bash
python main.py cli
```

**命令行单次执行**

```bash
python main.py cli "查询薪资最高的3个员工"
```

**WebUI 模式**

```bash
python main.py webui
```

浏览器自动打开 `http://127.0.0.1:8000`

## 项目结构

```text
agent_gzh/
├── core/               # 核心模块
│   ├── agent.py        # Agent 主循环
│   ├── llm.py          # LLM 抽象层
│   ├── skills.py       # Skill 加载器
│   └── tools.py        # 工具注册表
├── tools_builtin/      # 内置工具
│   ├── file_ops.py     # read / write
│   ├── shell.py        # bash
│   └── skill_ops.py    # activate_skill
├── skills/             # 可插拔技能
│   ├── hello-world/    # 示例技能
│   └── sqlite-sample/  # 数据库查询技能
├── adapters/           # 界面适配器
│   ├── cli.py          # 命令行
│   └── server.py       # WebUI 后端
├── webui/              # 前端页面
│   └── index.html
├── data/               # 示例数据
│   ├── sample.db
│   └── seed_sample_db.py
├── logs/               # 日志目录
├── uploads/            # 上传文件目录
├── config.yaml         # 主配置
├── main.py             # 统一入口
└── requirements.txt    # 依赖清单
```

## 配置说明

编辑 `config.yaml` 可切换 LLM 提供商：

```yaml
active_provider: kimi    # 可选: kimi / qwen / deepseek

providers:
  kimi:
    model: kimi-k2.5
  qwen:
    model: qwen-vl-max
  deepseek:
    model: deepseek-chat

skills:
  dir: ./skills
  enabled: null          # null = 全部启用

agent:
  max_iterations: 15
```

## 扩展 Skills

在 `skills/` 目录下创建新文件夹，放入 `SKILL.md` 文件即可自动生效。

SKILL.md 格式（遵循 agentskills.io 规范）：

```markdown
---
name: your-skill-name
description: 简短描述，说明做什么和何时使用
---

# 技能名称

## 使用说明

具体操作步骤...
```

## 许可证

MIT License

## 致谢

- [agentskills.io](https://agentskills.io) - Skill 规范标准
- [OpenAI](https://openai.com) - 兼容的 LLM API
```