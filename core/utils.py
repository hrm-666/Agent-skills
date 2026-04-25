import yaml
import base64
import mimetypes
from pathlib import Path

CONFIG_PATH = Path("config.yaml")
def load_config() -> dict:
    with open("config.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

def get_image_data_url(image_path: str) -> str:
    mime_type, _ = mimetypes.guess_type(image_path)
    if not mime_type or not mime_type.startswith("image/"):
        raise ValueError(f"无法识别的图片类型: {image_path}")
    with open(image_path, "rb") as f:
        data = base64.b64encode(f.read()).decode("utf-8")
    return f"data:{mime_type};base64,{data}"