"""
工具注册表
"""
import logging
from typing import Callable, Dict

logger = logging.getLogger(__name__)


class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, Dict] = {}

    def register(self, name: str, description: str, parameters: dict, handler: Callable):
        self._tools[name] = {
            "schema": {
                "type": "function",
                "function": {
                    "name": name,
                    "description": description,
                    "parameters": parameters,
                }
            },
            "handler": handler,
        }
        logger.debug(f"Tool registered: {name}")

    def get_openai_schemas(self) -> list:
        return [t["schema"] for t in self._tools.values()]

    def execute(self, name: str, arguments: dict) -> str:
        if name not in self._tools:
            return f"Error: Tool '{name}' not found. Available: {list(self._tools.keys())}"
        
        try:
            logger.info(f"Executing tool: {name}")
            result = self._tools[name]["handler"](**arguments)
            return str(result) if result is not None else ""
        except Exception as e:
            error_msg = f"Error executing '{name}': {e}"
            logger.exception(error_msg)
            return error_msg