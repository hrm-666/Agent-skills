"""Agent 主循环。"""

from __future__ import annotations

import base64
import json
import logging
import mimetypes
from pathlib import Path
from typing import Any, Callable

from .llm import LLM, LLMResponse, LLMToolCall, build_user_message
from .skills import SkillLoader
from .tools import ToolRegistry


class Agent:
    """执行一次完整的无状态 agent loop。"""

    def __init__(
        self,
        llm: LLM,
        skill_loader: SkillLoader,
        tool_registry: ToolRegistry,
        max_iterations: int = 15,
        logger: logging.Logger | None = None,
    ):
        self.llm = llm
        self.skill_loader = skill_loader
        self.tool_registry = tool_registry
        self.max_iterations = max_iterations
        self.logger = logger or logging.getLogger("mini_agent.agent")

    def run(
        self,
        user_text: str,
        image_paths: list[str] | None = None,
        on_step: Callable[[dict[str, Any]], None] | None = None,
    ) -> str:
        """执行一次完整的 agent loop。"""
        if not isinstance(user_text, str) or not user_text.strip():
            raise ValueError("user_text 必须是非空字符串")

        system = self._build_system_prompt()
        messages = [self._build_user_message(user_text=user_text, image_paths=image_paths)]
        tools = self.tool_registry.get_openai_schemas()
        last_progress = "尚无进展。"

        self.logger.info(
            "开始 agent run: text_length=%d, image_count=%d",
            len(user_text),
            len(image_paths or []),
        )
        self.logger.debug("system prompt: %s", system)
        self.logger.debug("initial messages: %s", messages)

        for iteration in range(1, self.max_iterations + 1):
            self.logger.info("开始第 %d 轮 agent loop", iteration)
            response = self.llm.complete(system=system, messages=messages, tools=tools)
            self.logger.debug("LLM 响应内容: %s", response.content)
            self.logger.debug("LLM tool_calls: %s", response.tool_calls)

            if response.tool_calls:
                messages.append(self._build_assistant_tool_call_message(response))
                for index, tool_call in enumerate(response.tool_calls, start=1):
                    result = self.tool_registry.execute(
                        tool_call.name,
                        tool_call.arguments,
                    )
                    last_progress = (
                        f"已执行工具 {tool_call.name}，返回结果长度 {len(result)} 字符。"
                    )

                    tool_message = {
                        "role": "tool",
                        "tool_call_id": tool_call.id or f"tool_call_{iteration}_{index}",
                        "name": tool_call.name,
                        "content": result,
                    }
                    messages.append(tool_message)

                    step = {
                        "type": "tool_call",
                        "name": tool_call.name,
                        "args": tool_call.arguments,
                        "result": result,
                    }
                    self._emit_step(on_step, step)
                continue

            final_reply = response.content.strip()
            if not final_reply:
                final_reply = "任务已完成，但模型没有返回文本结果。"

            self.logger.info("agent run 在第 %d 轮完成", iteration)
            return final_reply

        self.logger.warning("agent run 超过最大轮数: %d", self.max_iterations)
        return (
            f"任务未能在 {self.max_iterations} 轮内完成,已中止。"
            f"最后的进展是:{last_progress}"
        )

    def _build_system_prompt(self) -> str:
        """构造核心 system prompt。"""
        skill_catalog = self.skill_loader.get_catalog_text()
        return (
            "You are a task execution agent that uses tools and skills to help users.\n\n"
            "You have 4 built-in tools: read, write, bash, activate_skill.\n\n"
            "IMPORTANT: Before executing any specialized task, check if there is a "
            "relevant skill in the catalog below. If yes, use activate_skill(name) "
            "to load its full instructions before proceeding.\n\n"
            f"{skill_catalog}\n\n"
            "Rules:\n"
            "- Always use activate_skill before running a skill's scripts\n"
            "- After activating a skill, follow its SKILL.md instructions exactly\n"
            "- Keep responses concise unless the user asks for detail"
        )

    def _build_user_message(
        self,
        user_text: str,
        image_paths: list[str] | None = None,
    ) -> dict[str, Any]:
        """构造 user message，兼容未来图像输入。"""
        image_urls: list[str] = []
        text_suffixes: list[str] = []

        for image_path in image_paths or []:
            image_url = self._image_path_to_data_url(image_path)
            if image_url is None:
                text_suffixes.append(f"[image unavailable] {image_path}")
                continue
            image_urls.append(image_url)

        final_text = user_text.strip()
        if text_suffixes:
            final_text = f"{final_text}\n\n" + "\n".join(text_suffixes)

        return build_user_message(user_text=final_text, image_urls=image_urls or None)

    def _image_path_to_data_url(self, image_path: str) -> str | None:
        """将本地图像路径转换为 data URL。"""
        try:
            path = Path(image_path).expanduser()
            if not path.is_absolute():
                path = path.resolve()
            if not path.exists() or not path.is_file():
                self.logger.warning("图像文件不存在，已跳过: %s", image_path)
                return None

            mime_type, _ = mimetypes.guess_type(path.name)
            if mime_type is None or not mime_type.startswith("image/"):
                self.logger.warning("文件不是图像，已跳过: %s", path)
                return None

            encoded = base64.b64encode(path.read_bytes()).decode("ascii")
            return f"data:{mime_type};base64,{encoded}"
        except OSError as exc:
            self.logger.warning("读取图像文件失败，已跳过: %s (%s)", image_path, exc)
            return None

    def _build_assistant_tool_call_message(
        self, response: LLMResponse
    ) -> dict[str, Any]:
        """将标准化响应转换为 assistant tool_calls message。"""
        return {
            "role": "assistant",
            "content": response.content,
            "tool_calls": [self._serialize_tool_call(tool_call) for tool_call in response.tool_calls],
            "reasoning_content": response.reasoning_content or None,
        }

    def _serialize_tool_call(self, tool_call: LLMToolCall) -> dict[str, Any]:
        """序列化单个 tool_call，供下一轮消息回填。"""
        return {
            "id": tool_call.id or "",
            "type": "function",
            "function": {
                "name": tool_call.name,
                "arguments": json.dumps(tool_call.arguments, ensure_ascii=False),
            },
        }

    def _emit_step(
        self,
        on_step: Callable[[dict[str, Any]], None] | None,
        step: dict[str, Any],
    ) -> None:
        """安全地触发每轮步骤回调。"""
        if on_step is None:
            return
        try:
            on_step(step)
        except Exception:
            self.logger.exception("on_step 回调执行失败")
