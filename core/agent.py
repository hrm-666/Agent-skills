"""
Agent 主循环：无状态，每次 run() 独立执行。
支持流式输出、ToolResult 结构化结果、确认暂停。
"""
import json
import logging
from pathlib import Path
from types import SimpleNamespace
from typing import Callable, Optional, List, Dict, Tuple

from core.tools import ToolResult

logger = logging.getLogger(__name__)


class Agent:
    def __init__(
        self,
        llm,
        skill_loader,
        tool_registry,
        max_iterations: int = 15,
    ):
        self.llm = llm
        self.skill_loader = skill_loader
        self.tool_registry = tool_registry
        self.max_iterations = max_iterations

    def run(
        self,
        user_text: str,
        image_paths: Optional[list[str]] = None,
        history: Optional[List[Dict]] = None,
        on_step: Optional[Callable] = None,
        on_delta: Optional[Callable[[str], None]] = None,
    ) -> Tuple[str, List[Dict]]:
        """
        执行一次完整的 agent loop。
        返回 (最终回复文本, 步骤列表)。
        步骤格式：{"type": "tool_call", "name": ..., "args": ..., "result": ...}
        """
        logger.info(f"Agent 开始处理请求：{user_text[:100]}...")
        system = self._build_system_prompt()
        messages = list(history or [])
        messages.append(self._build_user_message(user_text, image_paths))
        steps: List[Dict] = []

        for iteration in range(1, self.max_iterations + 1):
            logger.info(f"第 {iteration} 轮 LLM 调用")
            tools = self.tool_registry.get_openai_schemas()

            if on_delta:
                try:
                    stream = self.llm.stream_complete(system, messages, tools)
                    msg = self._consume_stream(stream, on_delta)
                except Exception as e:
                    logger.warning(f"流式调用失败，回退：{e}")
                    msg = self.llm.complete(system, messages, tools)
            else:
                msg = self.llm.complete(system, messages, tools)

            if not msg.tool_calls:
                reply = msg.content or ""
                logger.info(f"Agent 完成，共 {iteration} 轮，回复长度 {len(reply)}")
                return reply, steps

            # 追加 assistant 消息（含 tool_calls）
            assistant_msg: Dict = {
                "role": "assistant",
                "content": msg.content,
                "tool_calls": msg.tool_calls,
            }
            if getattr(msg, "reasoning_content", None):
                assistant_msg["reasoning_content"] = msg.reasoning_content
            messages.append(assistant_msg)

            # 逐个执行工具
            for tc in msg.tool_calls:
                tool_name = tc["function"]["name"]
                try:
                    args = json.loads(tc["function"]["arguments"])
                except json.JSONDecodeError as e:
                    args = {}
                    result = ToolResult.failure(
                        "InvalidToolArguments",
                        f"工具参数不是合法 JSON：{e}",
                        recoverable=True,
                        meta={"raw_arguments": tc["function"]["arguments"]},
                    )
                else:
                    result = self.tool_registry.execute(tool_name, args)

                result_payload = result.to_dict()
                step = {"type": "tool_call", "name": tool_name, "args": args, "result": result_payload}
                steps.append(step)

                if on_step:
                    on_step(step)

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": json.dumps(result_payload, ensure_ascii=False),
                })

                if _error_type(result_payload) == "ConfirmationRequired":
                    reply = "该工具调用需要用户确认，当前任务已暂停。"
                    logger.info("Agent 暂停，等待用户确认工具调用")
                    return reply, steps

        # 超出最大轮次
        last = json.dumps(steps[-1]["result"], ensure_ascii=False)[:200] if steps else "无"
        reply = f"任务未能在 {self.max_iterations} 轮内完成，已中止。最后的进展是：{last}"
        logger.warning(f"Agent 超出最大迭代次数 {self.max_iterations}")
        return reply, steps

    def _build_system_prompt(self) -> str:
        catalog = self.skill_loader.get_catalog_text()
        tool_names = ", ".join(self.tool_registry.tools.keys()) or "(none)"
        return f"""You are a task execution agent that uses tools and skills to help users.

Available tools: {tool_names}.

Tool priority:
1. If a relevant skill exists, call activate_skill(name) first, then follow the skill instructions exactly.
2. If no skill fits but read/write/bash can solve the task, use the built-in tools.
3. If the task cannot be solved with available tools, say the capability is missing and suggest adding a skill.

For requests about current local state, files, folders, databases, command output, or the user's machine, do not answer from general knowledge. Inspect with tools.

{catalog}

Rules:
- Always use activate_skill BEFORE bash-ing into a skill's scripts
- After activating a skill, follow its SKILL.md instructions exactly
- Never merely tell the user what command to run when you can run it yourself
- After any mutating action, verify with a follow-up command before claiming success
- Tool results are JSON objects with ok/data/error/meta fields; inspect error.type before retrying
- If a tool returns ok=false, report the actual error and do not claim success
- If error.type is ConfirmationRequired, say the action is paused for confirmation; do not retry
- Keep responses concise unless user asks for detail
- Respond in the same language the user uses"""

    def _build_user_message(self, text: str, image_paths: Optional[list[str]]) -> dict:
        if not image_paths or not self.llm.supports_vision:
            return {"role": "user", "content": text}

        content = []
        for img_path in image_paths:
            content.append({
                "type": "image_url",
                "image_url": {"image_path": img_path},
            })
        content.append({"type": "text", "text": text})
        return {"role": "user", "content": content}

    def _consume_stream(self, stream, on_delta: Callable[[str], None]):
        """消费流式 chunk，聚合内容与 tool_calls。"""
        content_parts = []
        reasoning_parts = []
        tool_call_parts: Dict[int, Dict] = {}

        for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta

            text = getattr(delta, "content", None)
            if text:
                content_parts.append(text)
                on_delta(text)

            reasoning = _get_field(delta, "reasoning_content")
            if reasoning:
                reasoning_parts.append(reasoning)

            for tc in getattr(delta, "tool_calls", None) or []:
                idx = getattr(tc, "index", 0)
                item = tool_call_parts.setdefault(idx, {"id": "", "name": "", "arguments": ""})
                if getattr(tc, "id", None):
                    item["id"] = tc.id
                fn = getattr(tc, "function", None)
                if fn:
                    if getattr(fn, "name", None):
                        item["name"] += fn.name
                    if getattr(fn, "arguments", None):
                        item["arguments"] += fn.arguments

        tool_calls = []
        for idx in sorted(tool_call_parts):
            item = tool_call_parts[idx]
            if item["name"]:
                tool_calls.append({
                    "id": item["id"] or f"call_{idx}",
                    "type": "function",
                    "function": {"name": item["name"], "arguments": item["arguments"]},
                })

        return SimpleNamespace(
            content="".join(content_parts),
            reasoning_content="".join(reasoning_parts) or None,
            tool_calls=tool_calls or None,
        )


def _error_type(result: dict) -> Optional[str]:
    error = result.get("error")
    return error.get("type") if isinstance(error, dict) else None


def _get_field(obj, name: str):
    value = getattr(obj, name, None)
    if value is not None:
        return value
    extra = getattr(obj, "model_extra", None)
    if isinstance(extra, dict):
        return extra.get(name)
    if isinstance(obj, dict):
        return obj.get(name)
    return None
