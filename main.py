from __future__ import annotations

import argparse

import uvicorn

from adapters.cli import run_cli_once, run_interactive
from adapters.server import create_app
from core.runtime import load_config, setup_logging
from data.seed_sample_db import main as seed_db


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Mini Agent runtime")
    sub = parser.add_subparsers(dest="mode", required=True)

    cli_parser = sub.add_parser("cli", help="Run one message or interactive mode")
    cli_parser.add_argument("text", nargs="?", default="")
    cli_parser.add_argument("--interactive", action="store_true")
    cli_parser.add_argument("--provider", default=None)
    cli_parser.add_argument("--model", default=None)
    cli_parser.add_argument("--config", default="config.yaml")

    web_parser = sub.add_parser("webui", help="Start FastAPI web UI server")
    web_parser.add_argument("--config", default="config.yaml")

    setup_parser = sub.add_parser("setup", help="Seed sample sqlite database")
    setup_parser.add_argument("--config", default="config.yaml")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    config = load_config(getattr(args, "config", "config.yaml"))
    setup_logging(config.get("logging", {}).get("level", "INFO"))

    if args.mode == "setup":
        seed_db()
        return

    if args.mode == "cli":
        if args.interactive:
            run_interactive(config_path=args.config, provider=args.provider, model=args.model)
            return
        if not args.text:
            parser.error("cli mode requires text or --interactive")
        reply, steps = run_cli_once(args.text, config_path=args.config, provider=args.provider, model=args.model)
        for step in steps:
            print(f"[tool] {step['name']}: {step['result'][:200]}")
        print(reply)
        return

    if args.mode == "webui":
        web_cfg = config.get("webui", {})
        app = create_app(config_path=args.config)
        uvicorn.run(app, host=web_cfg.get("host", "127.0.0.1"), port=int(web_cfg.get("port", 8000)))


if __name__ == "__main__":
    main()
