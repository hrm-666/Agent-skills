from typing import Callable

class ToolRegistry:
    def __init__(self):
        self.tools: dict[str, dict] = {}  # name -> {schema, handler}

    def register(self, name: str, description: str, parameters: dict, handler: Callable):
        """注册一个工具"""

    def get_openai_schemas(self) -> list[dict]:
        """返回 OpenAI function calling 格式的 tools 列表"""

    def execute(self, name: str, arguments: dict) -> str:
        """
        执行工具。
        - 不存在的工具返回错误字符串(而不是抛异常,让 LLM 自己纠错)
        - 所有返回值都转成字符串
        """