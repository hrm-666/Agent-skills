from __future__ import annotations

import argparse
import logging
import sys

from adapters.cli import create_agent, format_confirmation_message, run_interactive
from core.agent import AgentConfirmationRequired
from core.logging_config import setup_logging

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")

    cli_parser = subparsers.add_parser("cli")
    cli_parser.add_argument("message", nargs="?")
    cli_parser.add_argument("--interactive", action="store_true")

    subparsers.add_parser("webui")
    return parser


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    setup_logging()

    parser = build_parser()
    args = parser.parse_args()
    logger.info("main command=%s", args.command or "webui")

    if args.command == "cli":
        if args.interactive:
            run_interactive()
            return 0
        if not args.message:
            parser.error("cli 模式需要提供消息，或使用 --interactive")
        try:
            print(create_agent().run(args.message))
        except AgentConfirmationRequired as exc:
            print(format_confirmation_message(exc))
        return 0

    if args.command in (None, "webui"):
        from adapters.server import run_server

        run_server()
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
