import logging
import base64
from typing import Literal, Optional, List, Dict, Any
from openai import OpenAI

ProviderName = Literal["kimi", "qwen", "deepseek"]

PROVIDERS = {
    "kimi": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",  # 适配用户提供的阿里云接口
        "default_model": "kimi-k2.5",
        "supports_vision": True,
        "env_key": "MOONSHOT_API_KEY",
    },
    "qwen": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "default_model": "qwen-max-latest",
        "supports_vision": True,
        "env_key": "DASHSCOPE_API_KEY",
    },
    "deepseek": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "default_model": "deepseek-r1",
        "supports_vision": False,
        "env_key": "DEEPSEEK_API_KEY",
    },
}

class LLM:
    def __init__(self, provider: ProviderName, api_key: str, model: Optional[str] = None, base_url: Optional[str] = None):
        self.config = PROVIDERS.get(provider)
        if not self.config:
            raise ValueError(f"Unsupported provider: {provider}")
        
        self.model = model or self.config["default_model"]
        url = base_url or self.config["base_url"]
        
        self.client = OpenAI(api_key=api_key, base_url=url)
        self.provider = provider
        logging.info(f"Initialized LLM with provider: {provider}, model: {self.model}")

    @property
    def supports_vision(self) -> bool:
        return self.config["supports_vision"]

    def _prepare_messages(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """处理深思/视觉等特殊逻辑"""
        new_messages = []
        for msg in messages:
            if msg["role"] == "user" and isinstance(msg["content"], list):
                # 如果是图片列表
                if not self.supports_vision:
                    logging.warning(f"Provider {self.provider} does not support vision. Converting images to text.")
                    content = ""
                    for item in msg["content"]:
                        if item["type"] == "text":
                            content += item["text"]
                        elif item["type"] == "image_url":
                            content += f"\n[Image: {item['image_url']['url'][:50]}...]"
                    new_messages.append({"role": "user", "content": content})
                else:
                    new_messages.append(msg)
            else:
                new_messages.append(msg)
        return new_messages

    def complete(self, system: str, messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]] = None) -> Any:
        full_messages = [{"role": "system", "content": system}] + self._prepare_messages(messages)
        
        params = {
            "model": self.model,
            "messages": full_messages,
        }
        if tools:
            params["tools"] = tools
            params["tool_choice"] = "auto"

        try:
            logging.debug(f"Calling LLM {self.provider} with {len(full_messages)} messages")
            response = self.client.chat.completions.create(**params)
            return response.choices[0].message
        except Exception as e:
            logging.error(f"LLM call failed: {str(e)}")
            raise e
