from typing import Callable
import logging

logger = logging.getLogger(__name__)

class ToolRegistry:
    def __init__(self):
        self.tools: dict[str, dict] = {}  # name -> {schema, handler}

    def register(self, name: str, description: str, parameters: dict, handler: Callable):
        """注册一个工具"""
        self.tools[name] = {
        "schema": {
            "type": "function",         
            "function": {                
                "name": name,
                "description": description,
                "parameters": parameters
            }
        },
        "handler": handler
    }

    def get_openai_schemas(self) -> list[dict]:
        """返回 OpenAI function calling 格式的 tools 列表"""
        return [self.tools[name]["schema"] for name in self.tools]
    
    def execute(self, name: str, arguments: dict) -> str:
        """
        执行工具。
        - 不存在的工具返回错误字符串(而不是抛异常,让 LLM 自己纠错)
        - 所有返回值都转成字符串
        """
        if name not in self.tools:
            available = ", ".join(self.tools.keys())
            logger.error("请求执行未知工具: %s. 可用: %s", name, available)
            return f"Error: tool '{name}' not found. Available: {available}"
        
        try:
            handler = self.tools[name]["handler"]
            logger.info("执行工具: %s, args=%s", name, arguments)
            result = handler(**arguments)
            logger.info("工具执行完成: %s, result_len=%s", name, len(str(result)) if result is not None else 0)
            return str(result)
        except Exception as e:
            logger.exception("工具执行异常: %s", name)
            return f"Error executing {name}: {str(e)}"