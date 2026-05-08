# Mini Agent — 当前实现技术解读

> 一个尽量小、尽量直、但仍然保留可扩展边界的 Python Agent Runtime

---

## 一、当前项目是否符合“最纯粹、最简洁、可扩展”

先说结论：

**核心代码基本符合。**

它现在已经具备下面这些特点：

1. 核心链路很短  
   从入口到模型调用再到工具执行，路径清晰，没有套多层抽象。

2. 能力边界明确  
   `Agent` 只管循环，`LLM` 只管调模型，`ToolRegistry` 只管工具，`SkillLoader` 只管技能。

3. 工具数很克制  
   只有 `read / write / bash / activate_skill` 四个内置工具，符合“少而精”的目标。

4. 扩展方式简单  
   新能力通过 `skills/` 新增目录接入，不需要改 `core/` 主循环。

5. 同时保留 CLI 和 WebUI  
   既适合调试，也适合展示，但适配层没有污染核心逻辑。

但如果严格按“整个工程都足够纯粹”的标准看，还差最后几处尾巴：

1. `image_paths` 这个名字已经不完全准确  
   现在它既可能是真图片，也可能只是上传文件路径。逻辑是对的，但命名还带着一点早期版本痕迹。

所以最准确的判断是：

> 你的项目现在已经基本符合“极简可扩展 Agent 工程”的目标。

---

## 二、一句话定位

这个项目不是一个“聊天机器人脚手架”，而是一个**最小执行型 Agent 内核**。

它解决的问题非常聚焦：

1. 让模型能调用工具
2. 让技能通过 `skills/` 目录按需接入
3. 让同一套 Agent 核心同时服务 CLI 和 WebUI

它当前最适合被理解成：

> 一个用于学习和演示 Agent loop、tool calling、skill 机制的极简运行时。

---

## 三、当前目录结构

当前真正属于项目主体的部分是：

```text
mhr/
├── main.py
├── config.yaml
├── requirements.txt
├── Task6.md
├── TECHNICAL_WALKTHROUGH.md
│
├── adapters/
│   ├── cli.py
│   └── server.py
│
├── core/
│   ├── agent.py
│   ├── llm.py
│   ├── tools.py
│   ├── skills.py
│   └── logging_config.py
│
├── tools_builtin/
│   ├── file_ops.py
│   ├── shell.py
│   └── skill_ops.py
│
├── skills/
│   └── hello-world/
│
├── webui/
│   └── index.html
│
├── uploads/
├── workspace/
└── logs/
```

如果只看核心运行时，真正关键的目录只有 4 个：

1. `core/`
2. `tools_builtin/`
3. `adapters/`
4. `skills/`

---

## 四、整体架构

### 4.1 分层结构

```text
┌─────────────────────────────────────────────────────┐
│                    Adapters                         │
│  CLI: adapters/cli.py                              │
│  Web: adapters/server.py + webui/index.html        │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│                      Core                           │
│  Agent        core/agent.py                        │
│  LLM          core/llm.py                          │
│  ToolRegistry core/tools.py                        │
│  SkillLoader  core/skills.py                       │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│                Built-in Tools / Skills             │
│  read / write / bash / activate_skill              │
│  skills/<name>/SKILL.md + scripts/*.py             │
└─────────────────────────────────────────────────────┘
```

### 4.2 每层各自负责什么

| 层级 | 负责内容 | 不负责内容 |
|---|---|---|
| `adapters/` | 接收输入、返回结果、启动服务 | 不负责智能决策 |
| `core/agent.py` | 组织 agent loop | 不负责具体工具实现 |
| `core/llm.py` | 调用不同 provider | 不负责决定何时调工具 |
| `core/tools.py` | 注册与执行工具 | 不负责具体业务逻辑 |
| `core/skills.py` | 扫描与加载 skill | 不负责运行 skill 脚本 |
| `tools_builtin/` | 提供基础能力 | 不负责模型推理 |

这就是它现在最漂亮的地方：

> 每个模块都不大，而且职责边界比较清楚。

---

## 五、一次请求是怎么跑通的

### 5.1 CLI 模式

以这条命令为例：

```bash
python main.py cli "你好"
```

执行链路是：

1. [main.py](/d:/大学/大三/大模型应用开发/task6/mhr/main.py:1) 解析命令行参数
2. `main.py` 调用 `create_agent()`
3. [adapters/cli.py](/d:/大学/大三/大模型应用开发/task6/mhr/adapters/cli.py:1) 读取配置、组装 Agent
4. [core/agent.py](/d:/大学/大三/大模型应用开发/task6/mhr/core/agent.py:1) 开始循环
5. [core/llm.py](/d:/大学/大三/大模型应用开发/task6/mhr/core/llm.py:1) 调用模型
6. 如果模型要求工具调用，交给 [core/tools.py](/d:/大学/大三/大模型应用开发/task6/mhr/core/tools.py:1)
7. 如果模型识别到 `hello-world` skill，会先调用 `activate_skill`
8. 再调用 `bash` 执行 [skills/hello-world/scripts/hello.py](/d:/大学/大三/大模型应用开发/task6/mhr/skills/hello-world/scripts/hello.py:1)
9. 工具结果回填给模型
10. 模型输出最终文本

### 5.2 WebUI 模式

以网页端为例：

1. 浏览器访问 `/`
2. [adapters/server.py](/d:/大学/大三/大模型应用开发/task6/mhr/adapters/server.py:1) 返回 [webui/index.html](/d:/大学/大三/大模型应用开发/task6/mhr/webui/index.html:1)
3. 前端调用 `/api/providers` 获取模型列表
4. 用户输入文本或上传图片后，前端调用 `/api/chat`
5. 后端把请求转成 `agent.run(...)`
6. 如果上传的是图片，`Agent` 会把图片转成多模态消息发给支持视觉的模型
7. 后端把最终 `reply` 和 `steps` 返回给前端
8. 前端渲染对话和工具步骤

---

## 六、核心模块解读

## 6.1 `main.py`

[main.py](/d:/大学/大三/大模型应用开发/task6/mhr/main.py:1) 很纯，职责只有三件事：

1. 解析命令
2. 初始化日志
3. 分发到 `cli / webui / setup`

支持的入口：

```bash
python main.py cli "消息内容"
python main.py cli --interactive
python main.py webui
```

它没有承担业务逻辑，这点是对的。

## 6.2 `adapters/cli.py`

[adapters/cli.py](/d:/大学/大三/大模型应用开发/task6/mhr/adapters/cli.py:1) 是当前项目的装配中心。

它负责：

1. 加载 `.env`
2. 读取 `config.yaml`
3. 选择 provider 和 API key
4. 创建 `SkillLoader`
5. 注册 4 个内置工具
6. 创建 `LLM`
7. 返回 `Agent`

这个文件虽然有一些展开式代码，但可读性是好的，因为它把“Agent 是怎么组装出来的”完整写在了一个地方。

## 6.3 `core/agent.py`

[core/agent.py](/d:/大学/大三/大模型应用开发/task6/mhr/core/agent.py:1) 是项目最核心的文件。

它做的事非常标准：

```python
1. 构造 system prompt
2. 构造 user message
3. 调用 llm.complete(...)
4. 如果有 tool_calls:
   - 逐个执行工具
   - 把结果塞回 messages
   - 继续下一轮
5. 如果没有 tool_calls:
   - 返回最终文本
```

当前它还有两个重要特点：

1. 无状态  
   每次 `run()` 都是独立调用，不保留历史对话。

2. 支持图片接入  
   如果传入 `image_paths`，会尝试把图片转成 base64 多模态消息。

这说明当前项目已经不只是“文本 Agent”了，而是具备了最小多模态输入能力。

## 6.4 `core/llm.py`

[core/llm.py](/d:/大学/大三/大模型应用开发/task6/mhr/core/llm.py:1) 是 provider 适配层。

它现在做的事很少，但很关键：

1. 管理 `kimi / qwen / deepseek` 三个 provider 的基础配置
2. 根据 provider 初始化 `OpenAI` 客户端
3. 暴露 `supports_vision`
4. 提供统一的 `complete(system, messages, tools)` 接口

这个文件很“薄”，这是优点，不是缺点。

## 6.5 `core/tools.py`

[core/tools.py](/d:/大学/大三/大模型应用开发/task6/mhr/core/tools.py:1) 负责：

1. 注册工具
2. 导出 OpenAI function calling 所需的 schema
3. 执行工具
4. 统一捕获工具异常

它现在仍然是最简版设计：

- 工具结果统一转字符串
- 错误也直接返回字符串
- 不做工具策略和确认机制

这让它非常容易理解，也符合你当前“保持纯粹”的目标。

## 6.6 `core/skills.py`

[core/skills.py](/d:/大学/大三/大模型应用开发/task6/mhr/core/skills.py:1) 定义了项目的扩展方式。

它负责：

1. 扫描 `skills/`
2. 找出每个 `SKILL.md`
3. 解析 frontmatter
4. 校验 `name` 和 `description`
5. 生成 skill catalog
6. 在需要时加载指定 skill 正文

这个设计的意义非常大：

> 模型一开始只看 skill 摘要，真正需要时再通过 `activate_skill` 获取详细说明。

这样能保持 system prompt 足够短，也让扩展方式保持统一。

---

## 七、内置工具

当前内置工具一共 4 个。

## 7.1 `read`

文件：[tools_builtin/file_ops.py](/d:/大学/大三/大模型应用开发/task6/mhr/tools_builtin/file_ops.py:1)

作用：

- 读取文本文件
- 超过 10000 字符截断
- 二进制文件报错

## 7.2 `write`

文件：[tools_builtin/file_ops.py](/d:/大学/大三/大模型应用开发/task6/mhr/tools_builtin/file_ops.py:1)

作用：

- 写入文本
- 自动创建目录
- 限制写入 `workspace / uploads / logs`

这给项目提供了最小写入安全边界。

## 7.3 `bash`

文件：[tools_builtin/shell.py](/d:/大学/大三/大模型应用开发/task6/mhr/tools_builtin/shell.py:1)

作用：

- 执行 shell 命令
- 返回 `stdout + stderr`
- 支持超时

这是当前最强的工具，也是 skill 真正落地的基础。

## 7.4 `activate_skill`

文件：[tools_builtin/skill_ops.py](/d:/大学/大三/大模型应用开发/task6/mhr/tools_builtin/skill_ops.py:1)

作用：

- 按名字加载 skill 正文
- 找不到时返回错误提示

它的价值在于把“技能发现”和“技能正文加载”分开了。

---

## 八、当前 skill

当前项目里，真正保留的 skill 只有一个：

## `hello-world`

文件：[skills/hello-world/SKILL.md](/d:/大学/大三/大模型应用开发/task6/mhr/skills/hello-world/SKILL.md:1)

它的职责不是提供复杂业务能力，而是验证这条链路是否成立：

1. 模型能看到 skill catalog
2. 模型会调用 `activate_skill`
3. skill 会指导模型运行脚本
4. `bash` 能执行 skill 脚本
5. 工具结果会回填给模型形成最终回答

所以它更像“机制样例 skill”，而不是业务 skill。

---

## 九、WebUI 现在承担什么职责

后端：[adapters/server.py](/d:/大学/大三/大模型应用开发/task6/mhr/adapters/server.py:1)  
前端：[webui/index.html](/d:/大学/大三/大模型应用开发/task6/mhr/webui/index.html:1)

当前网页端职责很简单：

1. 展示一个聊天页面
2. 拉取 provider 列表
3. 支持文本输入
4. 支持文件上传
5. 调用 `/api/chat`
6. 展示回复和工具步骤

当前 WebUI 的特点：

- 单文件实现
- 没有前端构建工具
- 适合演示和本地运行

当前它还没有做：

- SSE 流式输出
- 会话历史
- 更复杂的文件管理

但这不影响它作为一个极简适配层的成立。

---

## 十、配置文件现在的作用

[config.yaml](/d:/大学/大三/大模型应用开发/task6/mhr/config.yaml:1) 当前负责：

1. 默认 provider
2. provider 的 model 覆盖
3. skills 目录位置
4. agent 最大轮数
5. WebUI host / port

`.env` 则只负责存放 API key。

这种拆分是合理的：

- `.env` 存敏感信息
- `config.yaml` 存运行参数

---

## 十一、当前版本的优点与边界

## 11.1 优点

1. 主链路非常清楚
2. 核心模块职责分离比较干净
3. 工具数量少，适合学习和维护
4. skill 扩展方式已经成立
5. CLI 和 WebUI 都能跑通
6. 图片输入已经真正接入支持视觉的模型

## 11.2 当前边界

1. skill 还只有一个，更多是在验证机制
2. 工具返回值仍然是字符串，不够结构化
3. 没有工具安全策略层
4. WebUI 仍然是一次性返回，不是流式
5. 上传参数命名还偏早期版本风格，后续可以考虑统一成更通用的 `attachments`

---

## 十二、后续如果还想继续收缩，最值得动哪里

如果你继续坚持“极简优先”，后面最值得处理的是：

1. 决定 `image_paths` 是否重命名为更通用的 `attachments`
2. 如果以后新增第二个 skill，优先增加一个真正的业务 skill，而不是继续堆核心复杂度

但即使现在先不动，这个项目的核心结构也已经足够干净了。

---

## 十三、最终判断

当前这个版本，已经可以被比较准确地定义为：

> 一个以 `Agent loop + 4 个内置工具 + 文件系统 skill` 为核心的极简可扩展 Agent 工程。

它不是功能最全的版本，但从“纯粹、简洁、边界清楚、易于继续扩展”这几个标准看，已经基本成立。
