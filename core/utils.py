import yaml
import logging
from pathlib import Path

CONFIG_PATH = Path("config.yaml")
def load_config() -> dict:
    with open("config.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}





