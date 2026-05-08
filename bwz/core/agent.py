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

        text_preview = self._build_text_preview(user_text)
        self.logger.info(
            "收到请求: provider=%s, text=%s, image_count=%d",
            self.llm.provider,
            text_preview,
            len(image_paths or []),
        )
        self.logger.debug("system prompt: %s", system)

        for iteration in range(1, self.max_iterations + 1):
            self.logger.info(
                "开始第 %d 轮 LLM 调用: provider=%s, model=%s",
                iteration,
                self.llm.provider,
                getattr(self.llm, "model", "default"),
            )
            self.logger.debug(
                "messages payload: %s",
                json.dumps(
                    self._build_debug_messages_payload(system=system, messages=messages),
                    ensure_ascii=False,
                ),
            )
            response = self.llm.complete(system=system, messages=messages, tools=tools)
            self.logger.info(
                "第 %d 轮 LLM 调用完成: tool_calls=%d, content_length=%d",
                iteration,
                len(response.tool_calls),
                len(response.content or ""),
            )
            self.logger.debug(
                "tool_calls payload: %s",
                json.dumps(
                    self._build_debug_tool_calls_payload(response.tool_calls),
                    ensure_ascii=False,
                ),
            )
            self.logger.debug("LLM 响应内容: %s", response.content)

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
            "to load its full instructions. Don't guess - skills contain the exact "
            "commands and schemas you need.\n\n"
            f"{skill_catalog}\n\n"
            "Rules:\n"
            "- Always use activate_skill before running a skill's scripts\n"
            "- After activating a skill, follow its SKILL.md instructions exactly\n"
            "- For specialized tasks, check the skill catalog first before using bash\n"
            "- Keep responses concise unless the user asks for detail"
        )

    def _build_user_message(
        self,
        user_text: str,
        image_paths: list[str] | None = None,
    ) -> dict[str, Any]:
        """构造 user message，兼容图片与普通附件输入。"""
        image_urls: list[str] = []
        text_suffixes: list[str] = []
        supports_vision = self.llm.supports_vision

        for attachment_path in image_paths or []:
            attachment = self._inspect_attachment_path(attachment_path)
            if attachment is None:
                text_suffixes.append(f"[attachment unavailable] {attachment_path}")
                continue

            path, mime_type = attachment
            is_image = bool(mime_type and mime_type.startswith("image/"))

            if is_image and supports_vision:
                image_url = self._image_path_to_data_url(path, mime_type)
                if image_url is None:
                    text_suffixes.append(f"[attachment unavailable] {attachment_path}")
                    continue
                image_urls.append(image_url)
                continue

            if is_image and not supports_vision:
                self.logger.warning(
                    "当前 provider 不支持视觉输入，已将图片附件路径作为文本附加: %s",
                    path,
                )
                text_suffixes.append(f"[image attachment path for non-vision provider] {path}")
                continue

            self.logger.info("检测到非图片附件，已作为文本路径附加: %s", path)
            text_suffixes.append(f"[uploaded file attachment] {path}")

        final_text = user_text.strip()
        if text_suffixes:
            final_text = f"{final_text}\n\n" + "\n".join(text_suffixes)

        return build_user_message(user_text=final_text, image_urls=image_urls or None)

    def _inspect_attachment_path(self, attachment_path: str) -> tuple[Path, str | None] | None:
        """检查附件路径并返回规范化结果。"""
        try:
            path = Path(attachment_path).expanduser()
            if not path.is_absolute():
                path = path.resolve()
            if not path.exists() or not path.is_file():
                self.logger.warning("附件文件不存在，已跳过: %s", attachment_path)
                return None

            mime_type, _ = mimetypes.guess_type(path.name)
            return path, mime_type
        except OSError as exc:
            self.logger.warning("读取附件文件失败，已跳过: %s (%s)", attachment_path, exc)
            return None

    def _image_path_to_data_url(self, image_path: Path, mime_type: str | None) -> str | None:
        """将本地图像路径转换为 data URL。"""
        try:
            if mime_type is None or not mime_type.startswith("image/"):
                self.logger.warning("文件不是图像，无法转成 data URL: %s", image_path)
                return None

            encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
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

    def _build_text_preview(self, user_text: str, limit: int = 120) -> str:
        """把用户输入压缩成单行摘要，方便写入 INFO 日志。"""
        normalized = " ".join(user_text.strip().split())
        if len(normalized) <= limit:
            return normalized
        return normalized[:limit] + "...[truncated]"

    def _build_debug_messages_payload(
        self,
        system: str,
        messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """构造适合写入 DEBUG 日志的 messages payload。"""
        payload_messages: list[dict[str, Any]] = [{"role": "system", "content": system}]
        payload_messages.extend(self._serialize_debug_messages(messages))
        return payload_messages

    def _build_debug_tool_calls_payload(
        self,
        tool_calls: list[LLMToolCall],
    ) -> list[dict[str, Any]]:
        """构造适合写入 DEBUG 日志的 tool_calls payload。"""
        payload: list[dict[str, Any]] = []
        for tool_call in tool_calls:
            payload.append(
                {
                    "id": tool_call.id,
                    "name": tool_call.name,
                    "arguments": tool_call.arguments,
                }
            )
        return payload

    def _serialize_debug_messages(
        self,
        messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """把消息转换成适合写入 DEBUG 日志的结构。"""
        serialized_messages: list[dict[str, Any]] = []

        for message in messages:
            content = message.get("content")
            serialized_message: dict[str, Any] = {"role": message.get("role")}

            for key in ("tool_call_id", "name", "reasoning_content"):
                if key in message:
                    serialized_message[key] = message.get(key)

            if isinstance(content, str):
                serialized_message["content"] = content
            elif isinstance(content, list):
                blocks: list[dict[str, Any]] = []
                for block in content:
                    if not isinstance(block, dict):
                        blocks.append({"type": "unknown"})
                        continue

                    block_type = block.get("type")
                    if block_type == "text":
                        blocks.append({"type": "text", "text": str(block.get("text", ""))})
                        continue

                    if block_type == "image_url":
                        image_url = str(block.get("image_url", {}).get("url", ""))
                        blocks.append(
                            {
                                "type": "image_url",
                                "summary": "image_url omitted in debug log",
                                "url_length": len(image_url),
                            }
                        )
                        continue

                    blocks.append({"type": str(block_type or "unknown")})

                serialized_message["content"] = blocks
            else:
                serialized_message["content"] = str(type(content).__name__)

            tool_calls = message.get("tool_calls")
            if isinstance(tool_calls, list):
                serialized_calls: list[dict[str, Any]] = []
                for tool_call in tool_calls:
                    if not isinstance(tool_call, dict):
                        serialized_calls.append({"type": "unknown"})
                        continue
                    serialized_calls.append(tool_call)
                serialized_message["tool_calls"] = serialized_calls

            serialized_messages.append(serialized_message)

        return serialized_messages
