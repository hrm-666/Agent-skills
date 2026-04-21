#!/usr/bin/env python3
"""Mini Agent 统一入口。"""

import argparse
import yaml
from core.logging_config import setup_logging

with open("config.yaml", encoding="utf-8") as f:
    setup_logging(yaml.safe_load(f) or {})

from adapters.cli import run


def main() -> None:
    parser = argparse.ArgumentParser(description="Mini Agent")
    subparsers = parser.add_subparsers(dest="command", required=True, help="子命令")

    # cli 子命令
    cli_parser = subparsers.add_parser("cli", help="使用 CLI 模式发送消息")
    cli_parser.add_argument("message", help="发送给 Agent 的消息")
    cli_parser.add_argument("--provider", choices=["kimi", "zai", "deepseek"], default=None)

    # setup 子命令
    subparsers.add_parser("setup", help="初始化示例数据库 data/sample.db")

    args = parser.parse_args()

    if args.command == "cli":
        print(run(args.message, provider=args.provider))
    elif args.command == "setup":
        from data.seed_sample_db import seed
        seed()


if __name__ == "__main__":
    main()
