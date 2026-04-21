# Mini Agent: 极简版插件化智能体

本项目是一个基于 Python 的极简 Agent Runtime，旨在演示 Agent Loop、工具调用（Tool Use）以及基于文件的技能（Skills）插件化加载机制。

## 核心特性
- **极简内核**：由 `read`, `write`, `bash`, `activate_skill` 四个原子工具驱动。
- **技能插件化**：遵守 `agentskills.io` 规范，放入 `skills/` 目录即可动态扩展能力。
- **多模型支持**：兼容 OpenAI 协议，支持 Kimi、通义千问、DeepSeek 等大模型。
- **双模交互**：支持命令行 (CLI) 与 现代化的 WebUI 界面。
- **零依赖构建**：无需 Webpack/Vite，纯原生前端体验。

## 目录结构
```text
mini-agent/
├── core/             # Agent 核心逻辑 (LLM适配器、工具注册、技能加载)
├── tools_builtin/    # 内置核心工具 (文件操作、Shell执行)
├── skills/           # 外部技能插件 (hello-world, sqlite-sample 等)
├── adapters/         # 交互入口 (CLI, FastAPI Web Server)
├── data/             # 示例数据与 SQLite 数据库
├── webui/            # WebUI 静态文件
├── logs/             # 运行日志
└── main.py           # 统一启动入口
```

## 5 分钟快速开始

### 1. 安装依赖
```bash
pip install -r requirements.txt
```

### 2. 配置环境
复制 `.env.example` 并重命名为 `.env`，填入您的 API Key：
```bash
cp .env.example .env
```

### 3. 初始化数据
```bash
python main.py setup
```

### 4. 启动应用
- **Web 界面**：`python main.py webui` (访问 http://127.0.0.1:8000/webui/index.html)
- **命令行**：`python main.py cli --interactive`

## 如何添加新技能？
1. 在 `skills/` 目录下创建新文件夹 (如 `my-skill`)。
2. 创建 `SKILL.md`，使用 YAML Frontmatter 定义名称与描述。
3. 在 `scripts/` 下编写核心执行逻辑 (Python/Shell)。
4. 重启 Agent，它将自动识别并学会使用新技能。

## 许可证
遵守 [agentskills.io](https://agentskills.io) 开放标准。
