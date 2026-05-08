# Mini Agent (Task6)

一个极简 Python Agent Runtime，演示 agent loop、tool use 和 skills 即插即用机制。

## 1. 快速开始（约5分钟）

1. 安装依赖

```bash
pip install -r requirements.txt
```

1. 配置环境变量

- 复制 `.env.example` 为 `.env`
- 至少填写一个密钥：
  - `OPENROUTER_API_KEY`
  - `DEEPSEEK_API_KEY`

1. 初始化示例数据库

```bash
python main.py setup
```

1. 运行 CLI

```bash
python main.py cli "你好,我叫小明"
```

1. 运行 WebUI

```bash
python main.py webui
```

打开 `http://127.0.0.1:8000`。

## 2. 目录说明

- `core/`: 核心运行时（LLM、Agent loop、skills、tools）
- `tools_builtin/`: 4 个内置工具（read/write/bash/activate_skill）
- `skills/`: 可插拔技能目录
- `adapters/`: CLI 与 FastAPI 入口
- `webui/`: 单文件前端
- `data/`: sqlite 示例数据库与种子脚本

## 3. 模型与Provider

- `openrouter`:
  - `moonshotai/kimi-k2.5`
  - `qwen/qwen-vl-plus`
  - `tencent/hy3-preview:free`
- `deepseek`:
  - `deepseek-chat`

通过 `config.yaml` 设置默认 provider/model；WebUI 可运行时切换。

## 4. 如何新增 Skill

1. 在 `skills/` 下创建新目录，例如 `skills/my-skill/`
1. 新建 `SKILL.md`，包含合法 frontmatter：

```yaml
---
name: my-skill
description: Describe what it does and when to use it.
---
```

1. 添加脚本到 `scripts/`，由 skill 指导模型通过 `bash` 调用。
1. 重启程序后自动生效。

## 5. 日志与故障排查

- 日志文件位于 `logs/agent-YYYY-MM-DD.log`
- 常见问题：
  - 缺少密钥：检查 `.env`
  - sqlite 查询失败：先运行 `python main.py setup`
  - 工具报错：查看日志中的 `bash call` 与返回内容
