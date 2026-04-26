#!/usr/bin/env python3
import sys
import logging

logger = logging.getLogger(__name__)

name = sys.argv[1] if len(sys.argv) > 1 else "朋友"
msg = f"你好,{name}!Mini Agent 已经正常运作。"
logger.info(msg)
print(msg)
