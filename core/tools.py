import logging
from typing import Callable

logger = logging.getLogger(__name__)

class ToolRegistry:
    def __init__(self):
        self.tools: dict[str, dict] = {}  # name -> {schema, handler}

    def register(self, schema:dict, handler: Callable):
        """注册一个工具"""
        self.tools[schema["function"]["name"]] = {"schema": schema, "handler": handler}

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