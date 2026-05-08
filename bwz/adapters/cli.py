"""CLI 适配层。"""

from __future__ import annotations

import json
import sys
from typing import Any, Callable, Protocol, TextIO


class AgentLike(Protocol):
    """CLI 适配层依赖的最小 Agent 接口。"""

    def run(
        self,
        user_text: str,
        image_paths: list[str] | None = None,
        on_step: Callable[[dict[str, Any]], None] | None = None,
    ) -> str: ...


def run_cli_once(
    agent: AgentLike,
    message: str,
    *,
    image_paths: list[str] | None = None,
    show_steps: bool = False,
    output: TextIO | None = None,
) -> str:
    """执行一次 CLI 请求并输出最终回复。"""
    if not isinstance(message, str) or not message.strip():
        raise ValueError("message 必须是非空字符串")

    output_stream = output or sys.stdout
    steps: list[dict[str, Any]] = []
    on_step = steps.append if show_steps else None

    reply = agent.run(
        user_text=message.strip(),
        image_paths=image_paths,
        on_step=on_step,
    )

    if show_steps and steps:
        _print_steps(steps, output_stream)

    print(reply, file=output_stream)
    return reply


def run_cli_repl(
    agent: AgentLike,
    *,
    show_steps: bool = False,
    input_func: Callable[[str], str] = input,
    output: TextIO | None = None,
) -> None:
    """启动无状态 CLI REPL。"""
    output_stream = output or sys.stdout
    print("Mini Agent interactive mode. Type exit or quit to leave.", file=output_stream)

    while True:
        try:
            user_text = input_func("mini-agent> ")
        except EOFError:
            print("", file=output_stream)
            print("已退出交互模式。", file=output_stream)
            break
        except KeyboardInterrupt:
            print("", file=output_stream)
            print("已退出交互模式。", file=output_stream)
            break

        normalized = user_text.strip()
        if not normalized:
            continue
        if normalized.lower() in {"exit", "quit"}:
            print("已退出交互模式。", file=output_stream)
            break

        run_cli_once(
            agent,
            normalized,
            show_steps=show_steps,
            output=output_stream,
        )
        print("", file=output_stream)


def _print_steps(steps: list[dict[str, Any]], output: TextIO) -> None:
    """在 CLI 中打印工具调用过程。"""
    for step in steps:
        if step.get("type") != "tool_call":
            continue

        tool_name = step.get("name", "unknown")
        args = json.dumps(step.get("args", {}), ensure_ascii=False)
        print(f"[tool] {tool_name} {args}", file=output)

        result = str(step.get("result", ""))
        preview = result if len(result) <= 300 else result[:300] + "...[truncated]"
        print(preview, file=output)
