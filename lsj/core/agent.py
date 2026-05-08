from __future__ import annotations

import base64
import json
import mimetypes
from pathlib import Path
from typing import Callable, Optional


class Agent:
    def __init__(self, llm, skill_loader, tool_registry, max_iterations: int = 15):
        self.llm = llm
        self.skill_loader = skill_loader
        self.tool_registry = tool_registry
        self.max_iterations = max_iterations

    def run(self, user_text: str, image_paths: Optional[list[str]] = None, on_step: Optional[Callable] = None) -> str:
        messages = [self._build_user_message(user_text, image_paths or [])]
        tools = self.tool_registry.get_openai_schemas()
        system = self._build_system_prompt()
        last_progress = ""
        last_tool_output = ""

        for iteration in range(1, self.max_iterations + 1):
            response = self.llm.complete(system=system, messages=messages, tools=tools)
            tool_calls = response.tool_calls or []

            assistant_message = {"role": "assistant", "content": response.content or ""}
            if tool_calls:
                assistant_message["tool_calls"] = [
                    {
                        "id": call.id,
                        "type": "function",
                        "function": {
                            "name": call.function.name,
                            "arguments": call.function.arguments,
                        },
                    }
                    for call in tool_calls
                ]
            messages.append(assistant_message)

            if not tool_calls:
                if response.content:
                    return response.content
                if last_tool_output:
                    return last_tool_output
                return "任务已完成，但模型没有返回文本内容。"

            for call in tool_calls:
                tool_name = call.function.name
                args_raw = call.function.arguments or "{}"
                try:
                    args = json.loads(args_raw)
                    if not isinstance(args, dict):
                        raise ValueError("Arguments must be a JSON object")
                except Exception as exc:
                    result = f"[error] Invalid tool arguments for '{tool_name}': {exc}. raw={args_raw}"
                    args = {}
                else:
                    result = self.tool_registry.execute(tool_name, args)
                    last_tool_output = result

                if on_step:
                    on_step(
                        {
                            "type": "tool_call",
                            "iteration": iteration,
                            "name": tool_name,
                            "args": args,
                            "result": result,
                        }
                    )

                messages.append({"role": "tool", "tool_call_id": call.id, "name": tool_name, "content": result})
                last_progress = result[:200]

        return f"任务未能在 {self.max_iterations} 轮内完成,已中止。最后的进展是: {last_progress}"

    def _build_system_prompt(self) -> str:
        skill_catalog = self.skill_loader.get_catalog_text()
        return f"""You are a task execution agent that uses tools and skills to help users.

You have 4 built-in tools: read, write, bash, activate_skill.

IMPORTANT: Before executing any specialized task, check if there is a relevant skill in the catalog below.
If yes, use activate_skill(name) to load its full instructions. Don't guess.

{skill_catalog}

Rules:
- Always use activate_skill BEFORE bash-ing into a skill's scripts
- After activating a skill, follow its SKILL.md instructions exactly
- When a user asks you to inspect files, folders, or command output, call a tool instead of saying you will inspect it.
- If a tool fails, either try a compatible alternative command or answer clearly from the error and prior context.
- Do not end with progress narration such as "I will try another way"; only give the final answer when the task is actually answered or blocked.
- Keep responses concise unless user asks for detail
"""

    def _build_user_message(self, user_text: str, image_paths: list[str]) -> dict:
        if not image_paths:
            return {"role": "user", "content": user_text}

        if not self.llm.supports_vision:
            suffix = "\n".join([f"[image path] {p}" for p in image_paths])
            return {"role": "user", "content": f"{user_text}\n{suffix}"}

        content = [{"type": "text", "text": user_text}]
        for path in image_paths:
            data_url = self._image_to_data_url(path)
            if data_url:
                content.append({"type": "image_url", "image_url": {"url": data_url}})
            else:
                content.append({"type": "text", "text": f"[image load failed] {path}"})
        return {"role": "user", "content": content}

    def _image_to_data_url(self, path: str) -> Optional[str]:
        p = Path(path)
        if not p.exists() or not p.is_file():
            return None
        mime_type = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
        raw = p.read_bytes()
        encoded = base64.b64encode(raw).decode("ascii")
        return f"data:{mime_type};base64,{encoded}"
