"""
文件操作工具: read, write
"""
from pathlib import Path


def read_file(path: str) -> str:
    """读取文本文件，最多 10000 字符"""
    file_path = Path(path)
    
    if not file_path.exists():
        return f"Error: File not found: {path}"
    
    if file_path.is_dir():
        return f"Error: '{path}' is a directory"
    
    try:
        content = file_path.read_text(encoding='utf-8')
        if len(content) > 10000:
            content = content[:10000] + "\n... [truncated]"
        return content
    except UnicodeDecodeError:
        return f"Error: Binary file cannot be read as text: {path}"
    except Exception as e:
        return f"Error reading file: {e}"


def write_file(path: str, content: str) -> str:
    """写入文件，只允许特定目录"""
    file_path = Path(path)
    
    # 安全限制：只允许写入特定目录
    allowed_prefixes = ["workspace/", "uploads/", "logs/", "data/"]
    if not any(str(file_path).startswith(p) or str(file_path).startswith(p.rstrip('/')) for p in allowed_prefixes):
        return f"Error: Write denied. Can only write to {allowed_prefixes}"
    
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding='utf-8')
        return f"Successfully wrote {len(content)} chars to {path}"
    except Exception as e:
        return f"Error writing file: {e}"