# Mini Agent

一个遵守 `agentskills.io` 思路的极简 Python Agent Runtime 练习项目。

## 当前状态

- 当前处于 Phase 0 脚手架整理阶段
- 核心目标是实现 `agent loop + tool use + skills 即插即用`
- 详细需求以根目录的 `Task6.md` 为开发依据

## 计划支持的入口

- `python main.py cli "消息内容"`
- `python main.py cli --interactive`
- `python main.py webui`
- `python main.py setup`

## Bootstrap 约定

后续实现会统一采用这一条初始化顺序：

1. 加载 `.env`
2. 读取 `config.yaml`
3. 初始化日志
4. 初始化 `SkillLoader` 并扫描 `skills/`
5. 初始化 `ToolRegistry` 并注册内置工具
6. 创建当前 provider 的 `LLM`
7. 创建 `Agent`

约定 `cli` 和 `webui` 复用同一个运行时装配入口，避免出现两套初始化逻辑。

后续 Phase 会逐步补齐实际实现。
