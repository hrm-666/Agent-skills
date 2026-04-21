from typing import Literal, Optional
from openai import OpenAI

ProviderName = Literal["kimi", "qwen", "deepseek"]

PROVIDERS = {
    "kimi": {
        "base_url": "https://api.moonshot.cn/v1",
        "default_model": "kimi-k2.5",
        "supports_vision": True,
        "env_key": "MOONSHOT_API_KEY",
    },
    "qwen": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "default_model": "qwen-vl-max",
        "supports_vision": True,
        "env_key": "DASHSCOPE_API_KEY",
    },
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "default_model": "deepseek-chat",
        "supports_vision": False,
        "env_key": "DEEPSEEK_API_KEY",
    },
}

class LLM:
    def __init__(self, provider: ProviderName, api_key: str, model: Optional[str] = None):
        """根据 provider 名字初始化 OpenAI 客户端"""
        provider_config = PROVIDERS[provider]
        self.provider = provider
        self.model = model or provider_config["default_model"]
        self._supports_vision = provider_config["supports_vision"]
        self.client = OpenAI(api_key=api_key, base_url=provider_config["base_url"])

    @property
    def supports_vision(self) -> bool:
        return self._supports_vision

    def complete(self, system: str, messages: list, tools: list) -> "LLMResponse":
        """
        调用 chat.completions.create
        返回结构化的 message(含 .content 和 .tool_calls)
        """
