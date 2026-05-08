import logging
from typing import Callable

logger = logging.getLogger(__name__)

class ToolRegistry:
    def __init__(self):
        self.tools: dict[str, dict] = {}  # name -> {schema, handler}

    def register(self, name: str, description: str, parameters: dict, handler: Callable):
        """注册一个工具"""
        logger.info("register tool name=%s", name)
        self.tools[name] = {
            "schema": {
                "type": "function",
                "function": {
                    "name": name,
                    "description": description,
                    "parameters": parameters
                },
            },
            "handler": handler
        }
    def get_openai_schemas(self) -> list[dict]:
        """返回 OpenAI function calling 格式的 tools 列表"""
        return [tool["schema"] for tool in self.tools.values()]

    def execute(self, name: str, arguments: dict) -> str:
        """
        执行工具。
        - 不存在的工具返回错误字符串(而不是抛异常,让 LLM 自己纠错)
        - 所有返回值都转成字符串
        """
        if name not in self.tools:
            logger.info("tool not found name=%s", name)
            return f"[error] Tool '{name}' not found."
        
        handler = self.tools[name]["handler"]
        logger.info("execute tool name=%s args_keys=%s", name, sorted(arguments.keys()))

        try:
            result = handler(**arguments)
        except Exception as e:
            logger.exception("tool failed name=%s", name)
            return f"[error] Tool '{name}' execution failed: {str(e)}"
        
        text = str(result)
        logger.info("tool done name=%s result_len=%s", name, len(text))
        return text
