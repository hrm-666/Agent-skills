import json
import logging
from typing import Optional, Callable

from core.llm import LLM
from core.skills import SkillLoader
from core.tools import ToolRegistry
from core.utils import get_image_data_url

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
        system_prompt = self._build_system_prompt()

        messages: list[dict] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text}
        ]

        if image_paths:
            if self.llm.supports_vision:
                for image_path in image_paths:
                    messages.append({
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {"url": f"{get_image_data_url(image_path)}"},
                            }
                        ]
                    })
            else:
                for image_path in image_paths:
                    messages.append({
                        "role": "user",
                        "content": f"url: {image_path}"
                    })

        tools = self.tool_registry.get_openai_schemas()

        logger.info(f"Agent.run started: user_text={user_text[:50]}..., image_paths={image_paths}")

        for iteration in range(self.max_iterations):
            logger.info(f"Agent iteration {iteration + 1}/{self.max_iterations}")

            response = self.llm.complete(
                system=system_prompt,
                messages=messages,
                tools=tools if tools else None
            )

            logger.info(f"LLM response: content_length={len(response.content) if response.content else 0}, tool_calls_count={len(response.tool_calls) if response.tool_calls else 0}")

            # 回调（用于 WebUI 进度展示）
            if on_step:
                on_step(response)

            # 处理工具调用
            if response.tool_calls:
                messages.append({
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "id": tool_call.id,
                            "type": tool_call.type,
                            "function": {
                                "name": tool_call.function.name,
                                "arguments": tool_call.function.arguments
                            }
                        }
                        for tool_call in response.tool_calls
                    ],
                    "reasoning_content": response.reasoning_content
                })
                for tool_call in response.tool_calls:
                    logger.info(f"Tool executed: name={tool_call.function.name}, arguments={tool_call.function.arguments[:100]}")
                    result = self.tool_registry.execute(
                        name=tool_call.function.name,
                        arguments=json.loads(tool_call.function.arguments)
                    )
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result
                    })
                continue

            # 无工具调用，返回内容
            if response.content is not None:
                logger.info(f"Agent.run completed: response_length={len(response.content)}")
                return response.content
            if iteration == self.max_iterations - 1:
                logger.warning("Agent exceeded max iterations")
                return f"任务未能在 15 轮内完成,已中止。最后的进展是:{response}"


    def _build_system_prompt(self) -> str:
        skill_catalog = self.skill_loader.get_catalog_text()
        return f"""You are a task execution agent that uses tools and skills to help users.

          You have 4 built-in tools: read, write, bash, activate_skill.

          IMPORTANT: Before executing any specialized task, check if there's a relevant skill in the catalog below. If yes, use
          activate_skill(name) to load its full instructions. Don't guess — skills contain the exact commands and schemas you
          need.

          {skill_catalog}

          Rules:
          - Always use activate_skill BEFORE bash-ing into a skill's scripts
          - After activating a skill, follow its SKILL.md instructions exactly
          - Keep responses concise unless user asks for detail"""