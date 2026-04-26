"""日志配置模块

极简实现：在程序入口调用 `setup_logging()` 即可将日志写入 `logs/agent-YYYY-MM-DD.log`，
同时在控制台打印 INFO 级别以上日志。
"""
import logging
import sys
from pathlib import Path
from datetime import datetime

# 确保日志目录存在
LOG_DIR = Path("logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)


def setup_logging():
    """配置全局日志系统，在主入口调用一次（幂等）。"""
    root = logging.getLogger()
    if root.handlers:
        return
    root.setLevel(logging.DEBUG)

    file_formatter = logging.Formatter(
        '[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    console_formatter = logging.Formatter(
        '[%(levelname)s] [%(name)s] %(message)s'
    )

    log_file = LOG_DIR / f"agent-{datetime.now().strftime('%Y-%m-%d')}.log"
    fh = logging.FileHandler(log_file, encoding='utf-8')
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(file_formatter)
    root.addHandler(fh)

    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(console_formatter)
    root.addHandler(ch)

    # 确认提示（不使用 logger 避免循环）
    print(f"日志系统已配置，日志文件: {log_file}")