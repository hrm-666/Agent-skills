import json
import logging
from typing import Callable, Optional

logger = logging.getLogger(__name__)

class Agent:
    def __init__(
        self,
        llm: "LLM",
        skill_loader: "SkillLoader",
        tool_registry: "ToolRegistry",
        max_iterations: int = 15,
    ):
        self.llm = llm
        self.skill_loader = skill_loader
        self.tool_registry = tool_registry
        self.max_iterations = max_iterations

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
        system = self._build_system_prompt()
        messages = [
            {"role": "user", "content": user_text}
        ]
        tools = self.tool_registry.get_openai_schemas()

        last_progress = ""
        logger.info("agent run start text_len=%s images=%s tools=%s", len(user_text), len(image_paths or []), len(tools))

        for iteration in range(1, self.max_iterations + 1):
            logger.info("agent iteration=%s llm_call messages=%s", iteration, len(messages))
            message = self.llm.complete(system, messages, tools)
            tool_calls = getattr(message, "tool_calls", None)

            if tool_calls:
                logger.info("agent iteration=%s tool_calls=%s", iteration, len(tool_calls))
                messages.append(message.model_dump(exclude_none=True))

                for tool_call in tool_calls:
                    tool_name = tool_call.function.name

                    try:
                        arguments = json.loads(tool_call.function.arguments or "{}")
                    except json.JSONDecodeError as exc:
                        arguments = {}
                        result = f"[error] Invalid tool arguments : {exc}"
                    else:
                        result = self.tool_registry.execute(tool_name, arguments)

                    last_progress = result
                    logger.info(
                        "agent tool_result name=%s result_len=%s",
                        tool_name,
                        len(result),
                    )

                    if on_step:
                        on_step({
                            "type": "tool_call",
                            "name": tool_name,
                            "args": arguments,
                            "result": result,
                        })

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result,
                    })

                continue
            logger.info("agent final response iteration=%s content_len=%s", iteration, len(message.content or ""))
            return message.content or ""
        
        logger.info("agent max_iterations reached max=%s last_progress_len=%s", self.max_iterations, len(last_progress))
        return f"[error] Agent failed to complete task within {self.max_iterations} iterations. Last progress: {last_progress}"
    def _build_system_prompt(self) -> str:
        skill_catalog = self.skill_loader.get_catalog_text()
        return f"""
    You are a task execution agent that uses tools and skills to help users.

    You have 4 built-in tools: read, write, bash, activate_skill.

    IMPORTANT: Before executing any specialized task, check if there's a relevant skill in the catalog below.
    If yes, use activate_skill(name) to load its full instructions. Don't guess - skills contain the exact commands and schemas you need.

    {skill_catalog}

    Rules:
    - Always use activate_skill BEFORE bash-ing into a skill's scripts
    - After activating a skill, follow its SKILL.md instructions exactly
    - Keep responses concise unless user asks for detail
    """.strip()

        
