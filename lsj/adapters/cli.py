from __future__ import annotations

import json

from core.runtime import build_agent, load_config, setup_logging


def run_cli_once(text: str, config_path: str = "config.yaml", provider: str | None = None, model: str | None = None):
    config = load_config(config_path)
    setup_logging(config.get("logging", {}).get("level", "INFO"))
    agent = build_agent(config, provider_override=provider, model_override=model)

    steps: list[dict] = []
    reply = agent.run(text, on_step=lambda s: steps.append(s))
    return reply, steps


def run_interactive(config_path: str = "config.yaml", provider: str | None = None, model: str | None = None):
    config = load_config(config_path)
    setup_logging(config.get("logging", {}).get("level", "INFO"))
    agent = build_agent(config, provider_override=provider, model_override=model)

    print("Mini Agent interactive mode. 输入 exit 退出。")
    while True:
        user_text = input("\nYou> ").strip()
        if not user_text:
            continue
        if user_text.lower() in {"exit", "quit"}:
            break

        steps: list[dict] = []
        reply = agent.run(user_text, on_step=lambda s: steps.append(s))
        for step in steps:
            args_text = json.dumps(step.get("args", {}), ensure_ascii=False)
            print(f"[tool] {step.get('name')} {args_text}")
        print(f"Agent> {reply}")
