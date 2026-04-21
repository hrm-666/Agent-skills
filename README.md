# mini-agent

这是一个严格参照 [`Task6.md`](./Task6.md) 创建出来的**框架性工程目录**，目的是先把 task6 要求中的项目结构、文件位置和模块边界搭出来，方便后续继续按教程逐步实现。

## 当前状态

当前仓库**还不是可运行成品**，也**不代表 task6 已完成**。

目前只完成了以下内容：

- 按 `Task6.md` 中的目标目录结构创建了工程骨架
- 补齐了教程中提到的大部分文件占位
- 放入了示例 `skills/`、`tools_builtin/`、`core/`、`adapters/`、`webui/` 等目录

当前**尚未保证**以下能力已经实现或可正常工作：

- Agent loop
- LLM 调用
- Skill 扫描与激活
- CLI 可用
- WebUI 可用
- `/api/chat`、`/api/upload`、`/api/providers` 可用
- 示例数据库与 sqlite skill 可用

换句话说，这个仓库目前更适合被理解为：

**“按照 task6 文档先搭出的项目框架，而不是已经完成实现的 mini-agent 项目。”**

## 使用说明

如果你是从 GitHub 看到这个仓库，请注意：

- 这里的代码主要用于对照 `Task6.md` 梳理目录结构
- 当前版本不承诺可以直接运行
- 后续需要继续按 Phase 1 / Phase 2 / Phase 3 逐步补全实现

## 目录说明

- `core/`: 教程中定义的核心模块位置
- `tools_builtin/`: 教程中的四个内置工具文件位置
- `skills/`: 教程中的示例技能目录
- `adapters/`: CLI 与 FastAPI 入口位置
- `webui/`: 单文件前端页面位置
- `data/`: 示例数据脚本位置
- `uploads/`: 上传目录
- `logs/`: 日志目录
