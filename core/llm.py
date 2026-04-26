from typing import Literal, Optional
from openai import OpenAI
from dotenv import load_dotenv
import os
import logging
import base64

logger = logging.getLogger(__name__)
ProviderName = Literal["kimi", "qwen", "deepseek"]

load_dotenv()
MOONSHOT_API_KEY = os.getenv("MOONSHOT_API_KEY")
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

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
    """LLM 返回的结构化 message，包含 content 和 tool_calls"""
    def __init__(self, content: Optional[str], tool_calls: Optional[list]):
        self.content = content
        self.tool_calls = tool_calls

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
        logger.info(f"LLM调用: provider={self.provider}, model={self.model}, tools数量={len(tools) if tools else 0}")
        full_messages = [{"role": "system", "content": system}] + messages
        
        for msg in full_messages:
            if isinstance(msg.get("content"), list):
                for item in msg["content"]:
                    if item.get("type") == "image_url" and "image_path" in item.get("image_url", {}):
                        path = item["image_url"]["image_path"]
                        with open(path, "rb") as f:
                            b64 = base64.b64encode(f.read()).decode()
                        ext = "png" if path.lower().endswith(".png") else "jpeg"
                        item["image_url"] = {"url": f"data:image/{ext};base64,{b64}"}

        kwargs = {
        "model": self.model,
        "messages": full_messages,
        "tools": tools if tools else None,
        "tool_choice": "auto" if tools else None,
        }

        if "kimi" in self.model:
            kwargs["extra_body"] = {
                "thinking": {
                    "type": "disabled"
                }
            }

        # 调用 LLM
        response = self.client.chat.completions.create(**kwargs)
        
        msg = response.choices[0].message
        
        tool_calls = None
        if msg.tool_calls:## tool_calls 是大模型返回的
            tool_calls = [{
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments
                }
            } for tc in msg.tool_calls]
            logger.info(f"LLM返回工具调用: {len(tool_calls)}个")
            logger.debug(f"完整 tool_calls: {tool_calls}")
        else:
            logger.info("LLM返回文本回复")
            logger.debug(f"回复内容: {msg.content}")
        return LLMResponse(content=msg.content, tool_calls=tool_calls)