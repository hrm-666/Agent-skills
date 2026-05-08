import logging
from types import SimpleNamespace
from typing import Literal, Optional
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
        "default_model": "deepseek-v4-flash",
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
        api_messages = self._build_messages(system, messages)
        logger.info("llm request provider=%s model=%s messages=%s tools=%s", self.provider, self.model, len(api_messages), len(tools))
        response = self.client.chat.completions.create(
            model=self.model,
            messages=api_messages,
            tools=tools,
        )

        message = response.choices[0].message
        logger.info(
            "llm response provider=%s model=%s has_tool_calls=%s content_len=%s",
            self.provider,
            self.model,
            bool(getattr(message, "tool_calls", None)),
            len(message.content or ""),
        )
        return message

    def stream_complete(self, system: str, messages: list, tools: list):
        api_messages = self._build_messages(system, messages)
        logger.info("llm stream request provider=%s model=%s messages=%s tools=%s", self.provider, self.model, len(api_messages), len(tools))
        return self.client.chat.completions.create(
            model=self.model,
            messages=api_messages,
            tools=tools,
            stream=True,
        )

    def collect_stream(self, stream, on_delta=None) -> "LLMResponse":
        content_parts: list[str] = []
        reasoning_parts: list[str] = []
        tool_call_parts: dict[int, dict[str, str]] = {}

        for chunk in stream:
            if not chunk.choices:
                continue

            delta = chunk.choices[0].delta
            text = getattr(delta, "content", None)
            if text:
                logger.info(
                    "llm stream delta provider=%s len=%s preview=%r",
                    self.provider,
                    len(text),
                    text[:40],
                )
                content_parts.append(text)
                if on_delta:
                    on_delta(text)

            reasoning_text = self._get_field(delta, "reasoning_content")
            if reasoning_text:
                reasoning_parts.append(reasoning_text)

            for tool_call in getattr(delta, "tool_calls", None) or []:
                index = getattr(tool_call, "index", 0)
                item = tool_call_parts.setdefault(index, {"id": "", "name": "", "arguments": ""})

                tool_call_id = getattr(tool_call, "id", None)
                if tool_call_id:
                    item["id"] = tool_call_id

                function = getattr(tool_call, "function", None)
                if not function:
                    continue

                name = getattr(function, "name", None)
                arguments = getattr(function, "arguments", None)
                if name:
                    item["name"] += name
                if arguments:
                    item["arguments"] += arguments

        tool_calls = []
        for index in sorted(tool_call_parts):
            item = tool_call_parts[index]
            if not item["name"]:
                continue
            tool_calls.append(SimpleNamespace(
                id=item["id"] or f"call_{index}",
                function=SimpleNamespace(name=item["name"], arguments=item["arguments"]),
            ))

        return SimpleNamespace(
            content="".join(content_parts),
            reasoning_content="".join(reasoning_parts) or None,
            tool_calls=tool_calls or None,
            model_dump=lambda exclude_none=True: {
                "role": "assistant",
                "content": "".join(content_parts) or None,
                **(
                    {"reasoning_content": "".join(reasoning_parts)}
                    if reasoning_parts
                    else {}
                ),
                **(
                    {
                        "tool_calls": [
                            {
                                "id": tool_call.id,
                                "type": "function",
                                "function": {
                                    "name": tool_call.function.name,
                                    "arguments": tool_call.function.arguments,
                                },
                            }
                            for tool_call in tool_calls
                        ]
                    }
                    if tool_calls
                    else {}
                ),
            },
        )

    def _build_messages(self, system: str, messages: list) -> list:
        api_messages = [
            {"role": "system", "content": system},
            *messages,
        ]
        return api_messages

    def _get_field(self, obj, name: str):
        value = getattr(obj, name, None)
        if value is not None:
            return value

        extra = getattr(obj, "model_extra", None)
        if isinstance(extra, dict):
            return extra.get(name)

        if isinstance(obj, dict):
            return obj.get(name)

        return None
