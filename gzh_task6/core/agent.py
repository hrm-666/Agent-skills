import json
import logging
from typing import Optional, Callable, List
from pathlib import Path

from .llm import LLM
from .skills import SkillLoader
from .tools import ToolRegistry
from tools_builtin import read_file, write_file, run_bash, make_activate_skill

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
        
        # activate_skill 需要绑定 skill_loader
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
        # 构造消息
        if image_paths and self.llm.supports_vision:
            # 多模态消息（简化版，实际需要转 base64）
            content = [{"type": "text", "text": user_text}]
            for img in image_paths:
                content.append({"type": "image_url", "image_url": {"url": f"file://{img}"}})
            messages = [{"role": "user", "content": content}]
        else:
            if image_paths and not self.llm.supports_vision:
                logger.warning(f"Provider {self.llm.provider} doesn't support vision, ignoring images")
            messages = [{"role": "user", "content": user_text}]

        system_prompt = self._build_system_prompt()
        tools = self.tool_registry.get_openai_schemas()
        
        for iteration in range(self.max_iterations):
            logger.info(f"Agent loop iteration {iteration + 1}")
            
            if on_step:
                on_step({"type": "thinking", "iteration": iteration})
            
            # 调用 LLM
            response = self.llm.complete(system_prompt, messages, tools)
            
            # 检查是否有工具调用
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
                    
                    # 执行工具
                    result = self.tool_registry.execute(tool_name, arguments)
                    
                    if on_step:
                        on_step({
                            "type": "tool_result",
                            "name": tool_name,
                            "result": result[:500] if len(result) > 500 else result,
                        })
                    
                    # 追加到消息历史
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
                continue  # 继续下一轮
            
            # 没有工具调用，返回最终答案
            final_answer = response.content or ""
            if on_step:
                on_step({"type": "complete", "answer": final_answer})
            
            return final_answer
        
        # 超过最大迭代次数
        error_msg = f"Task not completed within {self.max_iterations} rounds. Last response: {response.content if response else 'None'}"
        logger.warning(error_msg)
        return error_msg