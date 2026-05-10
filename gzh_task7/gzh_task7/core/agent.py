# import json
# import logging
# from typing import Optional, Callable, List, Generator
# from pathlib import Path

# from .llm import LLM
# from .skills import SkillLoader
# from .tools import ToolRegistry
# from tools_builtin import read_file, write_file, run_bash, make_activate_skill
# from .memory import get_memory, add_to_memory

# logger = logging.getLogger(__name__)


# class Agent:
#     def __init__(
#         self,
#         llm: LLM,
#         skill_loader: SkillLoader,
#         tool_registry: ToolRegistry,
#         max_iterations: int = 15,
#     ):
#         self.llm = llm
#         self.skill_loader = skill_loader
#         self.tool_registry = tool_registry
#         self.max_iterations = max_iterations
#         self.memory = get_memory()
#         self._register_builtin_tools()

#     def _register_builtin_tools(self):
#         """注册四个内置工具"""
#         self.tool_registry.register(
#             "read",
#             "Read the content of a text file. Returns up to 10,000 characters.",
#             {
#                 "type": "object",
#                 "properties": {"path": {"type": "string", "description": "File path (relative or absolute)"}},
#                 "required": ["path"]
#             },
#             read_file
#         )
        
#         self.tool_registry.register(
#             "write",
#             "Write text content to a file. Creates parent directories if needed.",
#             {
#                 "type": "object",
#                 "properties": {
#                     "path": {"type": "string"},
#                     "content": {"type": "string"}
#                 },
#                 "required": ["path", "content"]
#             },
#             write_file
#         )
        
#         self.tool_registry.register(
#             "bash",
#             "Execute a shell command. Returns stdout+stderr, truncated to 10,000 chars.",
#             {
#                 "type": "object",
#                 "properties": {
#                     "command": {"type": "string"},
#                     "timeout": {"type": "integer", "default": 60}
#                 },
#                 "required": ["command"]
#             },
#             run_bash
#         )
        
#         activate_skill_fn = make_activate_skill(self.skill_loader)
#         self.tool_registry.register(
#             "activate_skill",
#             "Load the full instructions of a specific skill. Use this BEFORE running any skill-related command.",
#             {
#                 "type": "object",
#                 "properties": {"name": {"type": "string", "description": "Skill name from catalog"}},
#                 "required": ["name"]
#             },
#             activate_skill_fn
#         )

#     def _build_system_prompt(self) -> str:
#         """构建系统提示"""
#         return f"""You are a task execution agent that uses tools and skills to help users.

# You have 4 built-in tools: read, write, bash, activate_skill.

# {self.skill_loader.get_catalog_text()}

# Rules:
# - Always use activate_skill BEFORE running any skill-related commands
# - After activating a skill, follow its SKILL.md instructions exactly
# - Keep responses concise unless user asks for detail

# Working directory: {Path.cwd()}
# """

#     def run(
#         self,
#         user_text: str,
#         image_paths: Optional[List[str]] = None,
#         on_step: Optional[Callable] = None,
#     ) -> str:
#         """执行 agent loop，支持记忆"""
#         # 获取记忆上下文
#         memory_messages = self.memory.get_context_messages()
        
#         # 构造用户消息
#         if image_paths and self.llm.supports_vision:
#             content = [{"type": "text", "text": user_text}]
#             for img in image_paths:
#                 content.append({"type": "image_url", "image_url": {"url": f"file://{img}"}})
#             current_messages = [{"role": "user", "content": content}]
#         else:
#             if image_paths and not self.llm.supports_vision:
#                 logger.warning(f"Provider {self.llm.provider} doesn't support vision, ignoring images")
#             current_messages = [{"role": "user", "content": user_text}]

#         # 合并记忆和当前消息
#         messages = memory_messages + current_messages
#         system_prompt = self._build_system_prompt()
#         tools = self.tool_registry.get_openai_schemas()
        
#         for iteration in range(self.max_iterations):
#             logger.info(f"Agent loop iteration {iteration + 1}")
            
#             if on_step:
#                 on_step({"type": "thinking", "iteration": iteration})
            
#             response = self.llm.complete(system_prompt, messages, tools)
            
#             if response.tool_calls:
#                 for tool_call in response.tool_calls:
#                     tool_name = tool_call["function"]["name"]
#                     arguments = json.loads(tool_call["function"]["arguments"])
                    
#                     if on_step:
#                         on_step({
#                             "type": "tool_call",
#                             "name": tool_name,
#                             "args": arguments,
#                         })
                    
#                     result = self.tool_registry.execute(tool_name, arguments)
                    
#                     if on_step:
#                         on_step({
#                             "type": "tool_result",
#                             "name": tool_name,
#                             "result": result[:500] if len(result) > 500 else result,
#                         })
                    
#                     messages.append({
#                         "role": "assistant",
#                         "content": None,
#                         "tool_calls": [tool_call]
#                     })
#                     messages.append({
#                         "role": "tool",
#                         "tool_call_id": tool_call["id"],
#                         "content": result
#                     })
#                 continue
            
#             final_answer = response.content or ""
#             if on_step:
#                 on_step({"type": "complete", "answer": final_answer})
            
#             # 保存到记忆
#             if final_answer:
#                 add_to_memory(user_text, final_answer)
            
#             return final_answer
        
#         error_msg = f"Task not completed within {self.max_iterations} rounds. Last response: {response.content if response else 'None'}"
#         logger.warning(error_msg)
#         return error_msg


import json
import logging
from typing import Optional, Callable, List, Generator
from pathlib import Path

from .llm import LLM
from .skills import SkillLoader
from .tools import ToolRegistry
from tools_builtin import read_file, write_file, run_bash, make_activate_skill
from .memory import get_memory, add_to_memory

logger = logging.getLogger(__name__)


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
        self.memory = get_memory()
        self._register_builtin_tools()

    def _register_builtin_tools(self):
        """注册四个内置工具"""
        self.tool_registry.register(
            "read",
            "Read the content of a text file. Returns up to 10,000 characters.",
            {
                "type": "object",
                "properties": {"path": {"type": "string", "description": "File path (relative or absolute)"}},
                "required": ["path"]
            },
            read_file
        )
        
        self.tool_registry.register(
            "write",
            "Write text content to a file. Creates parent directories if needed.",
            {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"}
                },
                "required": ["path", "content"]
            },
            write_file
        )
        
        self.tool_registry.register(
            "bash",
            "Execute a shell command. Returns stdout+stderr, truncated to 10,000 chars.",
            {
                "type": "object",
                "properties": {
                    "command": {"type": "string"},
                    "timeout": {"type": "integer", "default": 60}
                },
                "required": ["command"]
            },
            run_bash
        )
        
        activate_skill_fn = make_activate_skill(self.skill_loader)
        self.tool_registry.register(
            "activate_skill",
            "Load the full instructions of a specific skill. Use this BEFORE running any skill-related command.",
            {
                "type": "object",
                "properties": {"name": {"type": "string", "description": "Skill name from catalog"}},
                "required": ["name"]
            },
            activate_skill_fn
        )

    def _build_system_prompt(self) -> str:
        """构建系统提示"""
        return f"""You are a task execution agent that uses tools and skills to help users.

You have 4 built-in tools: read, write, bash, activate_skill.

{self.skill_loader.get_catalog_text()}

Rules:
- Always use activate_skill BEFORE running any skill-related commands
- After activating a skill, follow its SKILL.md instructions exactly
- Keep responses concise unless user asks for detail

Working directory: {Path.cwd()}
"""

    def run(
        self,
        user_text: str,
        image_paths: Optional[List[str]] = None,
        on_step: Optional[Callable] = None,
    ) -> str:
        """执行 agent loop，支持记忆"""
        # 获取记忆上下文
        memory_messages = self.memory.get_context_messages()
        
        # 构造用户消息
        if image_paths and self.llm.supports_vision:
            content = [{"type": "text", "text": user_text}]
            for img in image_paths:
                content.append({"type": "image_url", "image_url": {"url": f"file://{img}"}})
            current_messages = [{"role": "user", "content": content}]
        else:
            if image_paths and not self.llm.supports_vision:
                logger.warning(f"Provider {self.llm.provider} doesn't support vision, ignoring images")
            current_messages = [{"role": "user", "content": user_text}]

        # 合并记忆和当前消息
        messages = memory_messages + current_messages
        system_prompt = self._build_system_prompt()
        tools = self.tool_registry.get_openai_schemas()
        
        for iteration in range(self.max_iterations):
            logger.info(f"Agent loop iteration {iteration + 1}")
            
            if on_step:
                on_step({"type": "thinking", "iteration": iteration})
            
            response = self.llm.complete(system_prompt, messages, tools)
            
            if response.tool_calls:
                for tool_call in response.tool_calls:
                    tool_name = tool_call["function"]["name"]
                    arguments = json.loads(tool_call["function"]["arguments"])
                    
                    if on_step:
                        on_step({
                            "type": "tool_call",
                            "name": tool_name,
                            "args": arguments,
                        })
                    
                    result = self.tool_registry.execute(tool_name, arguments)
                    
                    if on_step:
                        on_step({
                            "type": "tool_result",
                            "name": tool_name,
                            "result": result[:500] if len(result) > 500 else result,
                        })
                    
                    messages.append({
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [tool_call]
                    })
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "content": result
                    })
                continue
            
            final_answer = response.content or ""
            if on_step:
                on_step({"type": "complete", "answer": final_answer})
            
            # 保存到记忆
            if final_answer:
                add_to_memory(user_text, final_answer)
            
            return final_answer
        
        error_msg = f"Task not completed within {self.max_iterations} rounds. Last response: {response.content if response else 'None'}"
        logger.warning(error_msg)
        return error_msg

    def run_stream(
        self,
        user_text: str,
        image_paths: Optional[List[str]] = None,
    ) -> Generator[dict, None, None]:
        """
        流式执行 agent loop，逐步产出内容。
        """
        # 获取记忆上下文
        memory_messages = self.memory.get_context_messages()
        
        # 构造用户消息
        if image_paths and self.llm.supports_vision:
            content = [{"type": "text", "text": user_text}]
            for img in image_paths:
                content.append({"type": "image_url", "image_url": {"url": f"file://{img}"}})
            current_messages = [{"role": "user", "content": content}]
        else:
            if image_paths and not self.llm.supports_vision:
                logger.warning(f"Provider {self.llm.provider} doesn't support vision, ignoring images")
            current_messages = [{"role": "user", "content": user_text}]

        # 合并记忆和当前消息
        messages = memory_messages + current_messages
        system_prompt = self._build_system_prompt()
        tools = self.tool_registry.get_openai_schemas()
        
        for iteration in range(self.max_iterations):
            logger.info(f"Agent loop iteration {iteration + 1}")
            
            # 调用 LLM
            response = self.llm.complete(system_prompt, messages, tools)
            
            # 检查是否有工具调用
            if response.tool_calls:
                for tool_call in response.tool_calls:
                    tool_name = tool_call["function"]["name"]
                    arguments = json.loads(tool_call["function"]["arguments"])
                    
                    yield {"type": "tool_call", "name": tool_name, "args": arguments}
                    
                    result = self.tool_registry.execute(tool_name, arguments)
                    
                    yield {"type": "tool_result", "name": tool_name, "result": result}
                    
                    messages.append({
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [tool_call]
                    })
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "content": result
                    })
                continue
            
            # 没有工具调用，流式输出最终回答
            full_content = ""
            for chunk in self.llm.complete_stream(system_prompt, messages, tools):
                if chunk:
                    full_content += chunk
                    yield {"type": "chunk", "content": chunk}
            
            # 保存到记忆
            if full_content:
                add_to_memory(user_text, full_content)
            
            yield {"type": "complete", "content": full_content}
            return
        
        error_msg = f"Task not completed within {self.max_iterations} rounds"
        logger.warning(error_msg)
        yield {"type": "error", "content": error_msg}