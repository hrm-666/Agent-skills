import base64
import logging
import mimetypes
from typing import Optional, List, Dict, Callable, Any

from .llm import LLM
from .skills import SkillLoader
from .tools import ToolRegistry


class Agent:
    def __init__(
        self,
        llm: LLM,
        skill_loader: SkillLoader,
        tool_registry: ToolRegistry,
        max_iterations: int = 15,
    ):
        self.llm = llm
        self.skill_loader = skill_loader
        self.tool_registry = tool_registry
        self.max_iterations = max_iterations

    def run(
        self,
        user_text: str,
        image_paths: Optional[List[str]] = None,
        on_step: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> str:
        messages = []
        content = [{"type": "text", "text": user_text}]

        if image_paths and self.llm.supports_vision:
            for path in image_paths:
                image_url = self._image_to_data_url(path)
                if image_url:
                    content.append({"type": "image_url", "image_url": {"url": image_url}})

        messages.append({"role": "user", "content": content})

        system_prompt = self._build_system_prompt()
        tools = self.tool_registry.get_openai_schemas()

        for i in range(self.max_iterations):
            logging.info("Iteration %s/%s", i + 1, self.max_iterations)
            response = self.llm.complete(system_prompt, messages, tools)

            msg_dict = {
                "role": "assistant",
                "content": response.content,
            }
            if response.tool_calls:
                msg_dict["tool_calls"] = [
                    {
                        "id": t.id,
                        "type": "function",
                        "function": {
                            "name": t.function.name,
                            "arguments": t.function.arguments,
                        },
                    }
                    for t in response.tool_calls
                ]
            messages.append(msg_dict)

            if on_step:
                on_step(
                    {
                        "type": "llm_output",
                        "content": response.content,
                        "tool_calls": response.tool_calls,
                    }
                )

            if not response.tool_calls:
                return response.content or ""

            for tool_call in response.tool_calls:
                name = tool_call.function.name
                args = tool_call.function.arguments
                result = self.tool_registry.execute(name, args)

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": name,
                        "content": result,
                    }
                )

                if on_step:
                    on_step({"type": "tool_result", "name": name, "args": args, "result": result})

        return "Agent reached the maximum number of iterations before producing a final answer."

    def _image_to_data_url(self, path: str) -> Optional[str]:
        local_path = path.lstrip("/").replace("/", "\\")
        try:
            mime_type, _ = mimetypes.guess_type(local_path)
            mime_type = mime_type or "image/png"
            with open(local_path, "rb") as image_file:
                encoded = base64.b64encode(image_file.read()).decode("ascii")
            return f"data:{mime_type};base64,{encoded}"
        except OSError as exc:
            logging.warning("Failed to attach image %s: %s", path, exc)
            return None

    def _build_system_prompt(self) -> str:
        skill_catalog = self.skill_loader.get_catalog_text()
        return f"""You are a task execution agent that uses tools and skills to help users.

You have 4 built-in tools: read, write, bash, activate_skill.

IMPORTANT: Before executing any specialized task, check if there is a
relevant skill in the catalog below. If yes, use activate_skill(name)
to load its full instructions. Skills contain the exact commands and
schemas you need.

{skill_catalog}

Rules:
- Always use activate_skill BEFORE bash-ing into a skill's scripts
- After activating a skill, follow its SKILL.md instructions exactly
- When a tool result contains enough information to answer the user, stop using tools and provide the final answer.
- Keep responses concise unless user asks for detail
"""
