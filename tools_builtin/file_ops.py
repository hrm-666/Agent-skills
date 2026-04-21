import os
from pathlib import Path

def read_file(path: str) -> str:
    """读取文本文件内容"""
    try:
        abs_path = os.path.abspath(path)
        if not os.path.exists(abs_path):
            return f"Error: File '{path}' not found."
        
        # 简单二进制检查
        with open(abs_path, 'rb') as f:
            chunk = f.read(1024)
            if b'\0' in chunk:
                return "Error: Cannot read binary file."
                
        with open(abs_path, 'r', encoding='utf-8') as f:
            content = f.read(10000)
            if f.read(1):
                content += "\n... (content truncated)"
            return content
    except Exception as e:
        return f"Error reading file: {str(e)}"

def write_file(path: str, content: str) -> str:
    """写入文本内容到文件"""
    try:
        abs_path = Path(path).absolute()
        workspace = Path(".").absolute()
        allowed_dirs = [
            workspace / "workspace",
            workspace / "uploads",
            workspace / "logs",
            workspace / "data"
        ]
        
        # 安全限制：只能写入指定目录
        is_allowed = any(abs_path.is_relative_to(d) for d in allowed_dirs)
        if not is_allowed:
            # MVP 特例：如果是在当前目录（非源码敏感目录）也可以
            # 但为了安全，严格遵守 Task6 文档提到的三个目录 + data
            return f"Error: Writing to '{path}' is not allowed for security reasons."

        abs_path.parent.mkdir(parents=True, exist_ok=True)
        abs_path.write_text(content, encoding='utf-8')
        return f"Successfully written to {path}"
    except Exception as e:
        return f"Error writing file: {str(e)}"
