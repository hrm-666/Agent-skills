from __future__ import annotations

from typing import Callable


class ToolRegistry:
    def __init__(self):
        self.tools: dict[str, dict] = {}

    def register(self, name: str, description: str, parameters: dict, handler: Callable):
        self.tools[name] = {
            "schema": {
                "type": "function",
                "function": {
                    "name": name,
                    "description": description,
                    "parameters": parameters,
                },
            },
            "handler": handler,
        }

    def get_openai_schemas(self) -> list[dict]:
        return [tool["schema"] for tool in self.tools.values()]

    def execute(self, name: str, arguments: dict) -> str:
        if name not in self.tools:
            return f"[error] Tool '{name}' not found. Available: {', '.join(sorted(self.tools.keys()))}"
        try:
            result = self.tools[name]["handler"](**arguments)
            return str(result)
        except Exception as exc:
            return f"[error] Tool '{name}' failed: {exc}"
