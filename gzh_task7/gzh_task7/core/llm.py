# 职责:封装三家 OpenAI-compatible 厂商,对外暴露统一接口

import os
import base64
import logging
from typing import Literal, Optional, List, Generator
from openai import OpenAI

logger = logging.getLogger(__name__)

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


class LLMResponse:
    """LLM 响应封装"""
    def __init__(self, content: Optional[str], tool_calls: Optional[list]):
        self.content = content
        self.tool_calls = tool_calls


class LLM:
    def __init__(self, provider: ProviderName, api_key: str, model: Optional[str] = None):
        provider_config = PROVIDERS[provider]
        self.provider = provider
        self.model = model or provider_config["default_model"]
        self._supports_vision = provider_config["supports_vision"]
        
        self.client = OpenAI(
            api_key=api_key,
            base_url=provider_config["base_url"],
        )
        logger.info(f"LLM initialized: {provider}/{self.model}")

    @property
    def supports_vision(self) -> bool:
        return self._supports_vision

    def complete(self, system: str, messages: list, tools: list) -> LLMResponse:
        """调用 LLM，返回响应"""
        full_messages = [{"role": "system", "content": system}] + messages
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=full_messages,
                tools=tools if tools else None,
                tool_choice="auto" if tools else None,
            )
            
            message = response.choices[0].message
            
            tool_calls = None
            if message.tool_calls:
                tool_calls = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        }
                    }
                    for tc in message.tool_calls
                ]
            
            return LLMResponse(content=message.content, tool_calls=tool_calls)
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            raise

    def complete_stream(self, system: str, messages: list, tools: list) -> Generator[str, None, None]:
        """
        流式调用 LLM，返回生成器，逐块产出内容
        注意：流式模式下不支持工具调用检测，仅用于纯文本回答
        """
        full_messages = [{"role": "system", "content": system}] + messages
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=full_messages,
                tools=tools if tools else None,
                tool_choice="auto" if tools else None,
                stream=True
            )
            
            for chunk in response:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
                    
        except Exception as e:
            logger.error(f"LLM stream call failed: {e}")
            yield f"错误: {e}"