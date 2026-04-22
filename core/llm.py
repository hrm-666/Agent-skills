import logging
from openai import OpenAI
from dataclasses import dataclass
from typing import Literal, Optional

logger = logging.getLogger(__name__)

ProviderName = Literal["kimi", "zai", "deepseek"]

PROVIDERS = {
    "kimi": {
        "base_url": "https://api.moonshot.cn/v1",
        "default_model": "kimi-k2.5",
        "supports_vision": True,
        "env_key": "MOONSHOT_API_KEY",
    },
    "zai": {
        "base_url": "https://open.bigmodel.cn/api/paas/v4/",
        "default_model": "glm-4.7",
        "supports_vision": True,
        "env_key": "ZAI_API_KEY",
    },
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "default_model": "deepseek-chat",
        "supports_vision": False,
        "env_key": "DEEPSEEK_API_KEY",
    },
}

@dataclass
class LLMResponse:
    content: str | None
    tool_calls: list
    reasoning_content: str | None = None


class LLM:
    def __init__(self, provider: ProviderName, api_key: str, model: Optional[str] = None):
        """根据 provider 名字初始化 OpenAI 客户端"""
        config = PROVIDERS[provider]

        self.provider = provider

        self.model = model or config["default_model"]

        self._supports_vision = config["supports_vision"]

        self.client = OpenAI(
            api_key=api_key,
            base_url=config["base_url"],
        )

    @property
    def supports_vision(self) -> bool:
        return self._supports_vision

    def complete(self, system: str, messages: list, tools: list) -> "LLMResponse":
        """
        调用 chat.completions.create
        返回结构化的 message(含 .content 和 .tool_calls)
        """
        all_messages = [{"role": "system", "content": system}] + messages

        logger.info(f"LLM complete called: provider={self.provider}, model={self.model}, message_count={len(messages)}")

        response = self.client.chat.completions.create(
            model=self.model,
            messages=all_messages,
            tools=tools,
        )

        logger.debug(f"LLM raw response: {response}")

        msg = response.choices[0].message

        return LLMResponse(
            content=msg.content,
            tool_calls=msg.tool_calls,
            reasoning_content=getattr(msg, "reasoning_content", None),
        )
