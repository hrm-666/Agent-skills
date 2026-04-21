from __future__ import annotations

import argparse
import sys
from pathlib import Path

from adapters.cli import run_cli, run_interactive
from adapters.server import run_server
from data.seed_sample_db import ensure_sample_db


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")

    cli_parser = subparsers.add_parser("cli")
    cli_parser.add_argument("message", nargs="?")
    cli_parser.add_argument("--interactive", action="store_true")

    subparsers.add_parser("webui")
    subparsers.add_parser("setup")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "setup":
        ensure_sample_db(Path("data") / "sample.db")
        print("sample.db 已初始化")
        return 0

    if args.command == "cli":
        if args.interactive:
            run_interactive()
            return 0
        if not args.message:
            parser.error("cli 模式需要提供消息，或使用 --interactive")
        print(run_cli(args.message))
        return 0

    if args.command in (None, "webui"):
        run_server()
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
