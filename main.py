#!/usr/bin/env python3
"""Mini Agent 统一入口。"""

import argparse
import yaml
from core.logging_config import setup_logging

with open("config.yaml", encoding="utf-8") as f:
    setup_logging(yaml.safe_load(f) or {})

from adapters.cli import run


def main() -> None:
    from pathlib import Path

    parser = argparse.ArgumentParser(description="Mini Agent")
    subparsers = parser.add_subparsers(dest="command", required=True, help="子命令")

    cli_parser = subparsers.add_parser("cli", help="使用 CLI 模式发送消息")
    cli_parser.add_argument("message", help="发送给 Agent 的消息")
    cli_parser.add_argument("--provider", choices=["kimi", "zai", "deepseek"], default=None)

    subparsers.add_parser("setup", help="初始化示例数据库 data/sample.db")

    webui_parser = subparsers.add_parser("webui", help="启动 WebUI")
    webui_parser.add_argument("--host", default=None)
    webui_parser.add_argument("--port", type=int, default=None)

    args = parser.parse_args()

    if args.command == "cli":
        print(run(args.message, provider=args.provider))
    elif args.command == "setup":
        from data.seed_sample_db import seed
        seed()
    elif args.command == "webui":
        import uvicorn
        from adapters.server import app
        cfg_path = Path("config.yaml")
        if cfg_path.exists():
            with open(cfg_path, encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
        else:
            config = {}
        webui_cfg = config.get("webui", {})
        host = args.host or webui_cfg.get("host", "127.0.0.1")
        port = args.port or webui_cfg.get("port", 8000)
        uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
