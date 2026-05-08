import logging
import re
from typing import Callable

logger = logging.getLogger(__name__)


class ToolConfirmationRequired(Exception):
    def __init__(self, tool_name: str, arguments: dict, message: str, risk: str = "high"):
        super().__init__(message)
        self.tool_name = tool_name
        self.arguments = arguments
        self.message = message
        self.risk = risk


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

    def execute(self, name: str, arguments: dict, confirmed: bool = False) -> str:
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

        block_message = self._check_blocked_operation(name, arguments)
        if block_message:
            logger.warning("tool blocked name=%s", name)
            return f"[error] {block_message}"

        confirmation_message = self._check_confirmation_required(name, arguments)
        if confirmation_message and not confirmed:
            logger.warning("tool confirmation required name=%s", name)
            raise ToolConfirmationRequired(name, arguments, confirmation_message)

        try:
            result = handler(**arguments)
        except Exception as e:
            logger.exception("tool failed name=%s", name)
            return f"[error] Tool '{name}' execution failed: {str(e)}"
        
        text = str(result)
        logger.info("tool done name=%s result_len=%s", name, len(text))
        return text

    def _check_blocked_operation(self, name: str, arguments: dict) -> str | None:
        if name != "bash":
            return None

        command = str(arguments.get("command", "")).strip().lower()
        blocked_patterns = [
            r"\brm\s+-rf\s+/$",
            r"\bshutdown\b",
            r"\breboot\b",
            r"\bformat\b",
            r"\bmkfs\b",
            r"\bdiskpart\b",
            r"\brd\s+/s\s+/q\s+c:\\",
            r"\bdel\s+/f\s+/s\s+/q\s+c:\\",
        ]
        for pattern in blocked_patterns:
            if re.search(pattern, command):
                return "This command is blocked because it looks destructive at the system level."
        return None

    def _check_confirmation_required(self, name: str, arguments: dict) -> str | None:
        if name != "bash":
            return None

        command = str(arguments.get("command", "")).strip()
        normalized = command.lower()
        confirm_patterns = [
            r"\brm\b",
            r"\bdel\b",
            r"\berase\b",
            r"\brmdir\b",
            r"\brd\s+/s\b",
            r"\bmv\b",
            r"\bmove\b",
            r"\bren\b",
            r"\brename\b",
            r"\bchmod\b",
        ]
        for pattern in confirm_patterns:
            if re.search(pattern, normalized):
                return f"Dangerous shell command requires confirmation before execution: {command}"
        return None
