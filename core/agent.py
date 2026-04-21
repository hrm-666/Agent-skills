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