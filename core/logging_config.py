"""Logging configuration — dual output: file (plain) + stdout (colored via rich)."""

import logging
from pathlib import Path
from rich.logging import RichHandler

LOGS_DIR = Path("./logs")
LOG_FORMAT = "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
LOG_FILE_PREFIX = "mini-agent"


def setup_logging(config: dict | None = None) -> None:
    """
    Configure logging with two handlers:
    1. File handler — logs/agent-YYYY-MM-DD.log, plain text, INFO+
    2. Console handler — stdout, colored via rich, INFO+

    Must be called once at startup, before any other logging calls.

    Args:
        config: Optional config dict with logging section.
               If provided, reads 'logging.dir', 'logging.level', etc.
    """
    config = config or {}
    log_config = config.get("logging", {})

    logs_dir = Path(log_config.get("dir", str(LOGS_DIR)))
    logs_dir.mkdir(parents=True, exist_ok=True)

    from datetime import datetime
    log_filename = f"{LOG_FILE_PREFIX}-{datetime.now().strftime('%Y-%m-%d')}.log"
    file_handler = logging.FileHandler(
        logs_dir / log_filename,
        encoding="utf-8"
    )
    file_handler.setLevel(log_config.get("level", logging.INFO))
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))

    console_handler = RichHandler(
        rich_tracebacks=True,
        tracebacks_show_locals=False,
        show_time=True,
        show_path=False,
    )
    console_handler.setLevel(log_config.get("level", logging.INFO))
    console_handler.setFormatter(logging.Formatter("%(message)s"))

    # Root logger configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(log_config.get("level", logging.INFO))
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)