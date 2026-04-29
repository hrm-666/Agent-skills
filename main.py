import argparse
import logging
import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

from adapters.cli import run_cli
from core.agent import Agent
from core.llm import LLM, PROVIDERS
from core.skills import SkillLoader
from core.tools import ToolRegistry
from tools_builtin.file_ops import read_file, write_file
from tools_builtin.shell import run_bash
from tools_builtin.skill_ops import activate_skill


def setup_logging() -> None:
    Path("logs").mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - [%(module)s] %(message)s",
        handlers=[
            logging.FileHandler("logs/agent.log", encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


def build_agent(config: dict) -> Agent:
    active_provider = config["active_provider"]
    provider_cfg = config["providers"][active_provider]
    env_key = PROVIDERS[active_provider]["env_key"]
    api_key = os.getenv(env_key)

    if not api_key:
        raise RuntimeError(f"API key for {active_provider} not found. Please set {env_key} in .env")

    llm = LLM(
        provider=active_provider,
        api_key=api_key,
        model=provider_cfg.get("model"),
        base_url=provider_cfg.get("base_url"),
    )

    skill_loader = SkillLoader(
        skills_dir=Path(config["skills"]["dir"]),
        enabled=config["skills"]["enabled"],
    )
    skill_loader.scan()

    tool_registry = ToolRegistry()
    tool_registry.register(
        "read",
        "Read the content of a text file. Returns up to 10,000 characters.",
        {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
        read_file,
    )
    tool_registry.register(
        "write",
        "Write text content to a file. Overwrites existing file.",
        {
            "type": "object",
            "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
            "required": ["path", "content"],
        },
        write_file,
    )
    tool_registry.register(
        "bash",
        "Execute a shell command. Use this to run scripts or command-line operations.",
        {
            "type": "object",
            "properties": {"command": {"type": "string"}, "timeout": {"type": "integer"}},
            "required": ["command"],
        },
        run_bash,
    )
    tool_registry.register(
        "activate_skill",
        "Load the full instructions of a specific skill. Use this before skill-related commands.",
        {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
        lambda name: activate_skill(name, skill_loader),
    )

    return Agent(
        llm=llm,
        skill_loader=skill_loader,
        tool_registry=tool_registry,
        max_iterations=config["agent"]["max_iterations"],
    )


def load_config() -> dict:
    config_path = Path("config.yaml")
    if not config_path.exists():
        raise FileNotFoundError("config.yaml not found")
    with config_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def main() -> None:
    load_dotenv()
    setup_logging()
    config = load_config()

    parser = argparse.ArgumentParser(description="Mini Agent Runtime")
    subparsers = parser.add_subparsers(dest="command", help="Sub-commands")

    cli_parser = subparsers.add_parser("cli", help="Run in CLI mode")
    cli_parser.add_argument("query", nargs="?", help="Initial query")
    cli_parser.add_argument("--interactive", action="store_true", help="Run in interactive mode")

    subparsers.add_parser("webui", help="Run in WebUI mode")
    subparsers.add_parser("setup", help="Initialize sample data")

    args = parser.parse_args()

    if args.command == "setup":
        print("Initializing sample data...")
        from data.seed_sample_db import seed_db

        seed_db()
        print("Setup complete.")
        return

    if args.command in {"cli", "webui"}:
        try:
            agent = build_agent(config)
        except Exception as exc:
            print(f"Error: {exc}")
            return

        if args.command == "cli":
            run_cli(agent, initial_query=args.query, interactive=args.interactive)
        else:
            from adapters.server import start_server

            start_server(agent, config["webui"]["host"], config["webui"]["port"])
        return

    parser.print_help()


if __name__ == "__main__":
    main()
