import json
import logging
from typing import Optional, List, Dict, Callable, Any
from .llm import LLM
from .skills import SkillLoader
from .tools import ToolRegistry

class Agent:
    def __init__(
        self,
        llm: LLM,
        skill_loader: SkillLoader,
        tool_registry: ToolRegistry,
        max_iterations: int = 15,
    ):
        self.llm = llm
        self.skill_loader = skill_loader
        self.tool_registry = tool_registry
        self.max_iterations = max_iterations

    def run(
        self,
        user_text: str,
        image_paths: Optional[List[str]] = None,
        on_step: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> str:
        """执行 Agent Loop"""
        messages = []
        
        # 构造初始多模态内容
        content = [{"type": "text", "text": user_text}]
        if image_paths and self.llm.supports_vision:
            for path in image_paths:
                # 这里假设传入的是 base64 或路径，实际 WebUI 需要处理转换
                # MVP 暂时只支持本地路径转换或已处理好的 URL
                content.append({"type": "image_url", "image_url": {"url": path}})
        
        messages.append({"role": "user", "content": content})
        
        system_prompt = self._build_system_prompt()
        tools = self.tool_registry.get_openai_schemas()

        for i in range(self.max_iterations):
            logging.info(f"Iteration {i+1}/{self.max_iterations}")
            
            response = self.llm.complete(system_prompt, messages, tools)
            
            # 将消息转换为字典以支持序列化和统一处理
            msg_dict = {
                "role": "assistant",
                "content": response.content,
            }
            if response.tool_calls:
                msg_dict["tool_calls"] = [
                    {
                        "id": t.id,
                        "type": "function",
                        "function": {
                            "name": t.function.name,
                            "arguments": t.function.arguments
                        }
                    } for t in response.tool_calls
                ]
            messages.append(msg_dict)

            if on_step:
                on_step({"type": "llm_output", "content": response.content, "tool_calls": response.tool_calls})

            if not response.tool_calls:
                return response.content or ""

            # 执行工具调用
            for tool_call in response.tool_calls:
                name = tool_call.function.name
                args = tool_call.function.arguments
                
                result = self.tool_registry.execute(name, args)
                
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": name,
                    "content": result
                })
                
                if on_step:
                    on_step({"type": "tool_result", "name": name, "args": args, "result": result})

        return "任务未能在最大迭代次数内完成。"

    def _build_system_prompt(self) -> str:
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
- Keep responses concise unless user asks for detail
"""
