from pathlib import Path
from typing import Optional, Callable
import json

from core.llm import LLM
from core.skills import SkillLoader
from core.tools import ToolRegistry
import logging

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
        logger.info(f"Agent初始化完成, max_iterations={max_iterations}")

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
        logger.info(f"收到用户请求: {user_text[:100]}")
        if image_paths:
            logger.info(f"附带图片: {image_paths}")
        # 1.构造初始消息
        messages = []
        if image_paths and self.llm.supports_vision:
            
            user_content = [{"type": "text", "text": user_text}]
            for img_path in image_paths:
                user_content.append({
                    "type": "image_url",
                    "image_url": {"image_path": img_path}
                })
            messages.append({"role": "user", "content": user_content})
        else:
            messages.append({"role": "user", "content": user_text})
        # 2.构建提示词
        system_prompt = self._build_system_prompt()
        # 3.获取工具列表
        tools = self.tool_registry.get_openai_schemas()
        # 4.执行 agent loop
        for iteration in range(self.max_iterations):
            # 调用 LLM
            logger.info(f"第 {iteration + 1} 轮迭代")
            logger.debug(f"当前消息列表: {messages}")
            response= self.llm.complete(
                system=system_prompt,
                messages=messages,
                tools=tools
            )
            content = response.content
            tool_calls = response.tool_calls
            # 如果没有工具调用，说明任务完成
            if not tool_calls:
                logger.info(f"任务完成，返回结果长度: {len(content) if content else 0}")
                return content or "任务完成"
            
            # 有工具调用：先记录 assistant 的回复
            messages.append({
                "role": "assistant",
                "content": content,
                "tool_calls": tool_calls
            })
            
            # 执行每个工具
            for tc in tool_calls:
                tool_name = tc["function"]["name"]
                tool_args = json.loads(tc["function"]["arguments"])
                logger.info(f"执行工具: {tool_name}, args={tool_args}")
                
                # 触发回调（用于 UI 展示）
                if on_step:
                    on_step({
                        "type": "tool_call",
                        "name": tool_name,
                        "args": tool_args
                    })
                
                # 执行工具
                result = self.tool_registry.execute(tool_name, tool_args)
                logger.info(f"工具执行结果: {tool_name}, result_len={len(result)}")

                # 触发回调（用于 UI 展示结果）
                if on_step:
                    on_step({
                        "type": "tool_result",
                        "name": tool_name,
                        "result": result
                    })
                
                # 把工具执行结果加到消息列表
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result
                })
        
        # 超过最大迭代次数
        logger.error(f"超过最大迭代次数: {self.max_iterations}")
        return f"任务未能在 {self.max_iterations} 轮内完成，已中止。"


    def _build_system_prompt(self) -> str:
        """
        构建 system prompt 
        """
        skill_catalog = self.skill_loader.get_catalog_text()
        
        return f"""You are a task execution agent that uses tools and skills to help users.

                You have 4 built-in tools: read, write, bash, activate_skill.

                IMPORTANT: Before executing any specialized task, check if there's a 
                relevant skill in the catalog below. If yes, use activate_skill(name) 
                to load its full instructions. Don't guess — skills contain the exact 
                commands and schemas you need.

                {skill_catalog}

                Rules:
                - Always use activate_skill BEFORE bash-ing into a skill's scripts
                - After activating a skill, follow its SKILL.md instructions exactly
                - Keep responses concise unless user asks for detail"""