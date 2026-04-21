import json
import logging
from typing import Callable, List, Dict, Any

class ToolRegistry:
    def __init__(self):
        self.tools: Dict[str, Dict[str, Any]] = {}

    def register(self, name: str, description: str, parameters: Dict[str, Any], handler: Callable):
        """注册一个工具"""
        self.tools[name] = {
            "schema": {
                "type": "function",
                "function": {
                    "name": name,
                    "description": description,
                    "parameters": parameters,
                }
            },
            "handler": handler
        }
        logging.info(f"Tool registered: {name}")

    def get_openai_schemas(self) -> List[Dict[str, Any]]:
        """返回 OpenAI function calling 格式的 tools 列表"""
        return [t["schema"] for t in self.tools.values()]

    def execute(self, name: str, arguments: str | Dict[str, Any]) -> str:
        """执行工具并返回字符串结果"""
        if name not in self.tools:
            return f"Error: Tool '{name}' not found."
        
        try:
            if isinstance(arguments, str):
                args = json.loads(arguments)
            else:
                args = arguments
                
            logging.info(f"Executing tool: {name} with args: {args}")
            handler = self.tools[name]["handler"]
            result = handler(**args)
            return str(result)
        except Exception as e:
            logging.error(f"Error executing tool {name}: {str(e)}")
            return f"Error: {str(e)}"
