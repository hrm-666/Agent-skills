"""LLM 抽象层。

职责：
- 封装 Kimi / Qwen / DeepSeek 三家 OpenAI-compatible 接口
- 对外暴露统一的 complete() 调用
- 兼容纯文本消息与带图片的消息
- 在 DeepSeek 不支持视觉输入时自动降级
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Any, Literal, Mapping

from openai import OpenAI


ProviderName = Literal["kimi", "qwen", "deepseek"]

PROVIDERS: dict[ProviderName, dict[str, Any]] = {
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


@dataclass
class ProviderStatus:
    """Provider 当前状态，用于 UI 或运行时检查。"""

    name: ProviderName
    supports_vision: bool
    configured: bool
    default_model: str
    env_key: str


@dataclass
class LLMToolCall:
    """标准化后的工具调用。"""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class LLMResponse:
    """标准化后的 LLM 响应。"""

    content: str
    tool_calls: list[LLMToolCall]
    reasoning_content: str
    raw_message: Any


def build_user_message(
    user_text: str, image_urls: list[str] | None = None
) -> dict[str, Any]:
    """构造兼容文本与图像输入的 user message。"""
    if not image_urls:
        return {"role": "user", "content": user_text}

    content: list[dict[str, Any]] = []
    for image_url in image_urls:
        content.append({"type": "image_url", "image_url": {"url": image_url}})
    content.append({"type": "text", "text": user_text})
    return {"role": "user", "content": content}


def get_provider_config(provider: ProviderName) -> dict[str, Any]:
    """获取单个 provider 的静态配置。"""
    if provider not in PROVIDERS:
        raise ValueError(f"不支持的 provider: {provider}")
    return PROVIDERS[provider]


def get_provider_env_key(provider: ProviderName) -> str:
    """获取 provider 对应的 API key 环境变量名。"""
    return str(get_provider_config(provider)["env_key"])


def is_provider_configured(
    provider: ProviderName,
    environ: Mapping[str, str] | None = None,
) -> bool:
    """判断 provider 的 API key 是否已配置。"""
    env = environ or os.environ
    env_key = get_provider_env_key(provider)
    return bool(str(env.get(env_key, "")).strip())


def list_provider_statuses(
    environ: Mapping[str, str] | None = None,
) -> list[ProviderStatus]:
    """返回所有 provider 的可用状态。"""
    statuses: list[ProviderStatus] = []
    for provider in sorted(PROVIDERS):
        provider_name = provider  # 保持类型收窄
        config = get_provider_config(provider_name)
        statuses.append(
            ProviderStatus(
                name=provider_name,
                supports_vision=bool(config["supports_vision"]),
                configured=is_provider_configured(provider_name, environ=environ),
                default_model=str(config["default_model"]),
                env_key=str(config["env_key"]),
            )
        )
    return statuses


class LLM:
    """统一的 LLM 调用入口。"""

    def __init__(
        self,
        provider: ProviderName,
        api_key: str,
        model: str | None = None,
        logger: logging.Logger | None = None,
    ):
        """根据 provider 名字初始化 OpenAI 客户端。"""
        config = get_provider_config(provider)
        if not api_key:
            env_key = str(config["env_key"])
            raise ValueError(f"{provider} 缺少 API Key，请检查环境变量 {env_key}")

        self.provider = provider
        self.provider_config = config
        self.model = model or self.provider_config["default_model"]
        self.logger = logger or logging.getLogger("mini_agent.llm")
        self.client = OpenAI(
            api_key=api_key,
            base_url=self.provider_config["base_url"],
        )

    @property
    def supports_vision(self) -> bool:
        """当前 provider 是否支持视觉输入。"""
        return bool(self.provider_config["supports_vision"])

    def complete(
        self, system: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> LLMResponse:
        """调用 chat.completions.create 并返回标准化结果。"""
        normalized_messages = self._normalize_messages(messages)
        if self.provider == "deepseek":
            normalized_messages = self._downgrade_images_for_deepseek(
                normalized_messages
            )

        prepared_messages = [{"role": "system", "content": system}, *normalized_messages]
        prepared_tools = self._validate_tools(tools)

        response = self.client.chat.completions.create(
            model=self.model,
            messages=prepared_messages,
            tools=prepared_tools or None,
        )
        message = response.choices[0].message
        return LLMResponse(
            content=self._extract_content(message),
            tool_calls=self._extract_tool_calls(message.tool_calls),
            reasoning_content=self._extract_reasoning_content(message),
            raw_message=message,
        )

    def _normalize_messages(
        self, messages: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """校验并标准化 messages。"""
        normalized: list[dict[str, Any]] = []
        for message in messages:
            if not isinstance(message, dict):
                raise ValueError("messages 中的每一项都必须是 dict")

            role = message.get("role")
            content = message.get("content")
            if role not in {"system", "user", "assistant", "tool"}:
                raise ValueError(f"不支持的 message role: {role}")
            if content is None:
                raise ValueError("message.content 不能为空")

            normalized_message = {"role": role, "content": self._normalize_content(content)}
            if "tool_call_id" in message:
                normalized_message["tool_call_id"] = message["tool_call_id"]
            if "name" in message:
                normalized_message["name"] = message["name"]
            if "tool_calls" in message:
                normalized_message["tool_calls"] = self._normalize_tool_calls(
                    message["tool_calls"]
                )
            if "reasoning_content" in message:
                reasoning_content = message["reasoning_content"]
                if reasoning_content is not None and not isinstance(reasoning_content, str):
                    raise ValueError("message.reasoning_content 必须是字符串或 None")
                normalized_message["reasoning_content"] = reasoning_content
            normalized.append(normalized_message)
        return normalized

    def _normalize_content(self, content: Any) -> Any:
        """兼容字符串内容与多模态内容块。"""
        if isinstance(content, str):
            return content
        if not isinstance(content, list):
            raise ValueError("message.content 必须是字符串或内容块列表")

        normalized_blocks: list[dict[str, Any]] = []
        for block in content:
            if not isinstance(block, dict):
                raise ValueError("内容块必须是 dict")

            block_type = block.get("type")
            if block_type == "text":
                text = block.get("text")
                if not isinstance(text, str):
                    raise ValueError("text 内容块必须包含字符串 text")
                normalized_blocks.append({"type": "text", "text": text})
                continue

            if block_type == "image_url":
                image_url = block.get("image_url")
                if not isinstance(image_url, dict) or not isinstance(
                    image_url.get("url"), str
                ):
                    raise ValueError("image_url 内容块必须包含 image_url.url 字符串")
                normalized_blocks.append(
                    {"type": "image_url", "image_url": {"url": image_url["url"]}}
                )
                continue

            raise ValueError(f"不支持的内容块类型: {block_type}")

        return normalized_blocks

    def _downgrade_images_for_deepseek(
        self, messages: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """DeepSeek 不支持视觉输入时，将图片降级为文本。"""
        downgraded_messages: list[dict[str, Any]] = []
        for message in messages:
            content = message["content"]
            if not isinstance(content, list):
                downgraded_messages.append(message)
                continue

            downgraded_blocks: list[dict[str, Any]] = []
            for block in content:
                if block["type"] != "image_url":
                    downgraded_blocks.append(block)
                    continue

                image_url = block["image_url"]["url"]
                self.logger.warning(
                    "DeepSeek 不支持视觉输入，已将图片输入降级为文本: %s",
                    image_url,
                )
                downgraded_blocks.append(
                    {
                        "type": "text",
                        "text": f"[image input downgraded for deepseek] {image_url}",
                    }
                )

            downgraded_messages.append(
                {
                    **message,
                    "content": downgraded_blocks,
                }
            )
        return downgraded_messages

    def _normalize_tool_calls(self, tool_calls: Any) -> list[dict[str, Any]]:
        """兼容 assistant message 中的 tool_calls 字段。"""
        if not isinstance(tool_calls, list):
            raise ValueError("message.tool_calls 必须是列表")

        normalized_calls: list[dict[str, Any]] = []
        for tool_call in tool_calls:
            if not isinstance(tool_call, dict):
                raise ValueError("tool_calls 中的每一项都必须是 dict")
            if tool_call.get("type") != "function":
                raise ValueError("assistant tool_call.type 必须为 'function'")

            function_spec = tool_call.get("function")
            if not isinstance(function_spec, dict):
                raise ValueError("assistant tool_call.function 必须是 dict")

            name = function_spec.get("name")
            arguments = function_spec.get("arguments")
            if not isinstance(name, str) or not name:
                raise ValueError("assistant tool_call.function.name 必须是非空字符串")
            if not isinstance(arguments, str):
                raise ValueError("assistant tool_call.function.arguments 必须是 JSON 字符串")

            normalized_calls.append(
                {
                    "id": str(tool_call.get("id", "")),
                    "type": "function",
                    "function": {
                        "name": name,
                        "arguments": arguments,
                    },
                }
            )
        return normalized_calls

    def _validate_tools(self, tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """确保 tools 符合 OpenAI function calling 格式。"""
        if not tools:
            return []
        if not isinstance(tools, list):
            raise ValueError("tools 必须是列表")

        validated_tools: list[dict[str, Any]] = []
        for tool in tools:
            if not isinstance(tool, dict):
                raise ValueError("tools 中的每一项都必须是 dict")
            if tool.get("type") != "function":
                raise ValueError("tool.type 必须为 'function'")

            function_spec = tool.get("function")
            if not isinstance(function_spec, dict):
                raise ValueError("tool.function 必须是 dict")

            name = function_spec.get("name")
            description = function_spec.get("description")
            parameters = function_spec.get("parameters")
            if not isinstance(name, str) or not name:
                raise ValueError("tool.function.name 必须是非空字符串")
            if not isinstance(description, str) or not description:
                raise ValueError("tool.function.description 必须是非空字符串")
            if not isinstance(parameters, dict):
                raise ValueError("tool.function.parameters 必须是 JSON schema dict")

            validated_tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": name,
                        "description": description,
                        "parameters": parameters,
                    },
                }
            )
        return validated_tools

    def _extract_content(self, message: Any) -> str:
        """提取 assistant 文本内容。"""
        content = getattr(message, "content", None)
        if content is None:
            return ""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    parts.append(str(block.get("text", "")))
                    continue
                text = getattr(block, "text", None)
                if isinstance(text, str):
                    parts.append(text)
            return "\n".join(part for part in parts if part).strip()
        return str(content)

    def _extract_reasoning_content(self, message: Any) -> str:
        """提取兼容厂商返回的 reasoning_content。"""
        reasoning_content = getattr(message, "reasoning_content", None)
        if reasoning_content is None:
            return ""
        if isinstance(reasoning_content, str):
            return reasoning_content
        return str(reasoning_content)

    def _extract_tool_calls(self, tool_calls: Any) -> list[LLMToolCall]:
        """将 OpenAI tool_calls 标准化为本地结构。"""
        normalized_calls: list[LLMToolCall] = []
        for tool_call in tool_calls or []:
            function = getattr(tool_call, "function", None)
            if function is None:
                continue

            raw_arguments = getattr(function, "arguments", "{}") or "{}"
            try:
                arguments = json.loads(raw_arguments)
            except json.JSONDecodeError:
                self.logger.warning("tool_call arguments 不是合法 JSON，将回退为空对象")
                arguments = {}

            normalized_calls.append(
                LLMToolCall(
                    id=getattr(tool_call, "id", ""),
                    name=getattr(function, "name", ""),
                    arguments=arguments,
                )
            )
        return normalized_calls
