#!/usr/bin/env python3
"""
从 B站 API 获取排行榜数据，保存到文件并返回路径
"""

import json
import urllib.request
from pathlib import Path
from datetime import datetime
from typing import Dict, List


def get_save_dir() -> str:
    """从 config.yaml 读取保存目录，默认 workspace"""
    config_path = Path(__file__).parent.parent.parent.parent / "config.yaml"
    if config_path.exists():
        try:
            import yaml
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                return config.get('save_dir', 'workspace')
        except:
            pass
    return 'workspace'


def fetch_ranking(rid: int = 0) -> Dict:
    """获取 B站排行榜数据"""
    url = f"https://api.bilibili.com/x/web-interface/ranking/v2?rid={rid}&type=all"
    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.bilibili.com"}
    req = urllib.request.Request(url, headers=headers)
    return json.loads(urllib.request.urlopen(req, timeout=15).read().decode('utf-8'))


def parse_items(data: Dict, top: int = 10) -> List[Dict]:
    """解析数据"""
    if data.get('code') != 0:
        return []
    items = data.get('data', {}).get('list', [])[:top]
    result = []
    for i, item in enumerate(items, 1):
        title = item.get('title', '').replace('<em class="keyword">', '').replace('</em>', '')
        result.append({
            "rank": i,
            "title": title,
            "author": item.get('owner', {}).get('name', '未知'),
            "bvid": item.get('bvid', ''),
            "url": f"https://www.bilibili.com/video/{item.get('bvid', '')}",
            "view": item.get('stat', {}).get('view', 0),
            "like": item.get('stat', {}).get('like', 0)
        })
    return result


def save_to_file(items: List[Dict], rid: int, top: int) -> str:
    """保存到文件，返回路径"""
    save_dir = Path(get_save_dir())
    save_dir.mkdir(parents=True, exist_ok=True)
    filename = f"bilibili_rank_{datetime.now().strftime('%Y%m%d_%H%M%S')}_rid{rid}_top{top}.json"
    filepath = save_dir / filename
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump({"total_count": len(items), "items": items}, f, ensure_ascii=False, indent=2)
    return str(filepath)


def get_rank(rid: int = 0, top: int = 10):
    """主入口"""
    try:
        data = fetch_ranking(rid)
        items = parse_items(data, top)
        if not items:
            print(json.dumps({"success": False, "error": "获取数据失败"}))
            return
        filepath = save_to_file(items, rid, top)
        print(json.dumps({"success": True, "file": filepath, "count": len(items)}))
    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}))


if __name__ == "__main__":
    import sys
    rid = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    top = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    get_rank(rid, top)