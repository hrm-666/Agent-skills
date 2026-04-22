import logging
from typing import Callable

from core.skills import get_skill_loader
from tools_builtin.shell import bash_tool
from tools_builtin.file_ops import read_tool,write_tool
from tools_builtin.skill_ops import activate_skill_tool

logger = logging.getLogger(__name__)

class ToolRegistry:
    def __init__(self):
        self.tools: dict[str, dict] = {}  # name -> {schema, handler}

    def register(self, schema:dict, handler: Callable):
        """注册一个工具"""
        tool_name = schema["function"]["name"]
        self.tools[tool_name] = {"schema": schema, "handler": handler}
        logger.info(f"register tool : {tool_name}")

    def get_openai_schemas(self) -> list[dict]:
        """返回 OpenAI function calling 格式的 tools 列表"""
        return [tool["schema"] for tool in self.tools.values()]

    def execute(self, name: str, arguments: dict) -> str:
        """
        执行工具。
        - 不存在的工具返回错误字符串(而不是抛异常,让 LLM 自己纠错)
        - 所有返回值都转成字符串
        """
        logger.info(f"ToolRegistry.execute: name={name}, arguments={arguments}")
        if name not in self.tools:
            return f"Error: Tool '{name}' not found."

        try:
            result = self.tools[name]["handler"](**arguments)
            return str(result)
        except Exception as e:
            return f"Error executing tool '{name}': {str(e)}"

def register_tools() -> ToolRegistry:
    tool_registry = ToolRegistry()
    tool_registry.register(*read_tool())
    tool_registry.register(*write_tool())
    tool_registry.register(*bash_tool())
    tool_registry.register(*activate_skill_tool(get_skill_loader()))

    return tool_registry