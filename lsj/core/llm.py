from __future__ import annotations

import logging
from copy import deepcopy
from typing import Literal, Optional

from openai import OpenAI

ProviderName = Literal["openrouter", "deepseek"]

PROVIDERS = {
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "default_model": "moonshotai/kimi-k2.5",
        "env_key": "OPENROUTER_API_KEY",
    },
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "default_model": "deepseek-chat",
        "env_key": "DEEPSEEK_API_KEY",
    },
}

VISION_MODEL_SUPPORT = {
    "moonshotai/kimi-k2.5": True,
    "qwen/qwen-vl-plus": True,
    "tencent/hy3-preview:free": False,
    "deepseek-chat": False,
}


class LLM:
    def __init__(self, provider: ProviderName, api_key: str, model: Optional[str] = None, base_url: Optional[str] = None):
        if provider not in PROVIDERS:
            raise ValueError(f"Unsupported provider: {provider}")
        cfg = PROVIDERS[provider]
        self.provider = provider
        self.model = model or cfg["default_model"]
        self.logger = logging.getLogger("mini_agent.llm")
        self.client = OpenAI(api_key=api_key, base_url=base_url or cfg["base_url"])

    @property
    def supports_vision(self) -> bool:
        return VISION_MODEL_SUPPORT.get(self.model, False)

    def complete(self, system: str, messages: list, tools: list):
        payload_messages = [{"role": "system", "content": system}] + deepcopy(messages)
        if not self.supports_vision:
            payload_messages = self._downgrade_vision_messages(payload_messages)
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=payload_messages,
                tools=tools if tools else None,
            )
        except Exception as exc:
            if tools and self._is_tool_use_unsupported_error(exc):
                self.logger.warning(
                    "Model %s does not support tool use on current provider route; retrying without tools.",
                    self.model,
                )
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=payload_messages,
                    tools=None,
                )
            else:
                raise
        return response.choices[0].message

    @staticmethod
    def _is_tool_use_unsupported_error(exc: Exception) -> bool:
        text = str(exc).lower()
        if "no endpoints found that support tool use" in text:
            return True
        if "tool use" in text and "no endpoints found" in text:
            return True
        if "function calling" in text and "not support" in text:
            return True

        status_code = getattr(exc, "status_code", None)
        if status_code == 404 and "openrouter" in text and "tool" in text:
            return True
        return False

    def _downgrade_vision_messages(self, messages: list) -> list:
        patched = []
        for msg in messages:
            content = msg.get("content")
            if not isinstance(content, list):
                patched.append(msg)
                continue
            text_parts = []
            had_image = False
            for part in content:
                if part.get("type") == "text":
                    text_parts.append(part.get("text", ""))
                elif part.get("type") == "image_url":
                    had_image = True
                    url = part.get("image_url", {}).get("url", "")
                    text_parts.append(f"[image omitted: {url[:120]}]")
            if had_image:
                self.logger.warning("Model %s does not support vision, image content downgraded to text.", self.model)
            patched.append({**msg, "content": "\n".join([p for p in text_parts if p]).strip()})
        return patched
