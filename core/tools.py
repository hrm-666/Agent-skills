"""工具注册表。"""

from __future__ import annotations

import logging
from typing import Any, Callable


class ToolRegistry:
    """统一管理工具 schema 与执行函数。"""

    def __init__(self, logger: logging.Logger | None = None):
        self.logger = logger or logging.getLogger("mini_agent.tools")
        self.tools: dict[str, dict[str, Any]] = {}

    def register(
        self,
        name: str,
        description: str,
        parameters: dict[str, Any],
        handler: Callable[..., Any],
    ) -> None:
        """注册一个工具。"""
        if not isinstance(name, str) or not name.strip():
            raise ValueError("工具名称必须是非空字符串")
        if not isinstance(description, str) or not description.strip():
            raise ValueError("工具描述必须是非空字符串")
        if not isinstance(parameters, dict):
            raise ValueError("工具 parameters 必须是 dict")
        if not callable(handler):
            raise ValueError("工具 handler 必须可调用")

        normalized_name = name.strip()
        if normalized_name in self.tools:
            self.logger.warning("工具已存在，将覆盖注册: %s", normalized_name)

        schema = {
            "type": "function",
            "function": {
                "name": normalized_name,
                "description": description.strip(),
                "parameters": parameters,
            },
        }
        self.tools[normalized_name] = {"schema": schema, "handler": handler}

    def get_openai_schemas(self) -> list[dict[str, Any]]:
        """返回 OpenAI function calling 格式的 tools 列表。"""
        return [self.tools[name]["schema"] for name in sorted(self.tools)]

    def execute(self, name: str, arguments: dict[str, Any]) -> str:
        """执行工具并统一返回字符串。"""
        if name not in self.tools:
            available = ", ".join(sorted(self.tools)) or "none"
            self.logger.warning("调用了未知工具: %s", name)
            return f"[error] unknown tool: {name}. Available tools: {available}"
        if not isinstance(arguments, dict):
            self.logger.warning("工具参数不是对象: tool=%s, args_type=%s", name, type(arguments).__name__)
            return f"[error] invalid arguments for tool '{name}': arguments must be an object"

        self.logger.info("执行工具: %s, args=%s", name, arguments)
        handler = self.tools[name]["handler"]

        try:
            result = handler(**arguments)
        except TypeError as exc:
            self.logger.exception("工具参数错误: %s", name)
            return f"[error] tool '{name}' arguments mismatch: {exc}"
        except Exception as exc:
            self.logger.exception("工具执行失败: %s", name)
            return f"[error] tool '{name}' failed: {exc}"

        result_text = str(result)
        self.logger.info(
            "工具执行完成: %s, result_length=%d, result_preview=%s",
            name,
            len(result_text),
            self._summarize_text(result_text),
        )
        return result_text

    def _summarize_text(self, text: str, limit: int = 160) -> str:
        """把工具返回值压缩成单行摘要，便于写入日志。"""
        normalized = " ".join(text.split())
        if len(normalized) <= limit:
            return normalized
        return normalized[:limit] + "...[truncated]"
