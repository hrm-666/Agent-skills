#!/usr/bin/env python3
"""
PledgeBox API 客户端 - 获取订单、统计、导出
"""

import sys
import json
import csv
import argparse
import urllib.request
import urllib.parse
import traceback
from pathlib import Path
from typing import Dict, List, Optional


# ============================================================
# 配置
# ============================================================

def load_config() -> Dict:
    """从 config.yaml 加载配置"""
    config = {"api_token": None, "project_id": None, "base_url": "https://api.pledgebox.com/api/openapi"}
    config_path = Path(__file__).parent.parent.parent.parent / "config.yaml"
    
    if config_path.exists():
        try:
            import yaml
            with open(config_path, 'r', encoding='utf-8') as f:
                pb_config = yaml.safe_load(f).get('pledgebox', {})
                config.update({k: pb_config.get(k, config[k]) for k in config})
        except Exception as e:
            print(f"DEBUG: 加载配置失败 - {e}", file=sys.stderr)
    else:
        print(f"DEBUG: config.yaml 不存在于 {config_path}", file=sys.stderr)
    
    return config


def get_save_dir() -> str:
    """获取保存目录"""
    config_path = Path(__file__).parent.parent.parent.parent / "config.yaml"
    if config_path.exists():
        try:
            import yaml
            with open(config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f).get('save_dir', 'workspace')
        except:
            pass
    return 'workspace'


# ============================================================
# API 请求
# ============================================================

HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://www.pledgebox.com/",
}


def api_get(endpoint: str, params: Dict = None) -> Dict:
    """GET 请求"""
    config = load_config()
    print(f"DEBUG: api_token={config['api_token'][:20]}...", file=sys.stderr)
    print(f"DEBUG: project_id={config['project_id']}", file=sys.stderr)
    
    if not config['api_token'] or not config['project_id']:
        print("DEBUG: API token 或 project_id 未配置", file=sys.stderr)
        return {"code": 401, "message": "API token 或 project_id 未配置", "data": [], "total_count": 0}
    
    url_params = {"api_token": config['api_token'], "project_id": config['project_id'], **(params or {})}
    url = f"{config['base_url']}/{endpoint}?{urllib.parse.urlencode(url_params)}"
    print(f"DEBUG: 请求 URL: {url[:100]}...", file=sys.stderr)
    
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            print(f"DEBUG: API 响应 code={data.get('code')}", file=sys.stderr)
            return data
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8') if e.fp else ''
        print(f"DEBUG: HTTPError {e.code} - {e.reason}", file=sys.stderr)
        print(f"DEBUG: 错误详情: {error_body[:200]}", file=sys.stderr)
        return {"code": e.code, "message": e.reason, "detail": error_body, "data": [], "total_count": 0}
    except Exception as e:
        print(f"DEBUG: 异常 - {type(e).__name__}: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return {"code": 500, "message": str(e), "data": [], "total_count": 0}


def get_orders(page: int = 1, **kwargs) -> Dict:
    """获取订单"""
    params = {"page": page}
    for k, v in kwargs.items():
        if v is not None:
            params[k] = 1 if k == 'is_completed' else v
    print(f"DEBUG: get_orders params={params}", file=sys.stderr)
    return api_get("orders", params)


# ============================================================
# 格式转换
# ============================================================

def to_simple_order(o: Dict) -> Dict:
    """精简格式"""
    return {
        "pbid": o.get("pbid"),
        "email": o.get("email"),
        "order_status": o.get("order_status"),
        "paid_amount": o.get("paid_amount"),
        "shipping_country": o.get("shipping_address", {}).get("country"),
        "backer_name": o.get("shipping_address", {}).get("name")
    }


def calc_stats(orders: List[Dict]) -> Dict:
    """统计"""
    if not orders:
        return {"error": "无数据"}
    total_paid = sum(float(o.get("paid_amount", 0)) for o in orders)
    status_count = {}
    for o in orders:
        s = o.get("order_status", "Unknown")
        status_count[s] = status_count.get(s, 0) + 1
    return {
        "total_orders": len(orders),
        "total_paid_amount": round(total_paid, 2),
        "average_paid": round(total_paid / len(orders), 2),
        "status_breakdown": status_count
    }


def save_json(data, path: str) -> Dict:
    """保存JSON"""
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return {"success": True, "message": f"已保存到 {path}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def save_csv(rows: List[Dict], path: str) -> Dict:
    """保存CSV"""
    if not rows:
        return {"success": False, "error": "无数据"}
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
        return {"success": True, "message": f"已保存到 {path}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ============================================================
# 主入口
# ============================================================

def main():
    print("DEBUG: main() 开始执行", file=sys.stderr)
    
    parser = argparse.ArgumentParser()
    parser.add_argument('--list', action='store_true')
    parser.add_argument('--stats', action='store_true')
    parser.add_argument('--email', type=str)
    parser.add_argument('--status', type=str)
    parser.add_argument('--completed', action='store_true')
    parser.add_argument('--page', type=int, default=1)
    parser.add_argument('--export-json', type=str)
    parser.add_argument('--export-csv', type=str)
    args = parser.parse_args()
    
    print(f"DEBUG: args={args}", file=sys.stderr)
    
    try:
        result = get_orders(
            page=args.page,
            email=args.email,
            order_status=args.status,
            is_completed=1 if args.completed else None
        )
        print(f"DEBUG: result code={result.get('code')}", file=sys.stderr)
        
        orders = result.get("data", [])
        print(f"DEBUG: 获取到 {len(orders)} 条订单", file=sys.stderr)
        
        if args.export_json:
            ret = save_json(result, args.export_json)
            print(json.dumps(ret))
        elif args.export_csv:
            rows = [{"pbid": o.get("pbid"), "email": o.get("email"), "order_status": o.get("order_status"), "paid_amount": o.get("paid_amount")} for o in orders]
            ret = save_csv(rows, args.export_csv)
            print(json.dumps(ret))
        elif args.stats:
            ret = calc_stats(orders)
            print(json.dumps(ret))
        elif args.list:
            output = {"total_count": result.get("total_count", len(orders)), "orders": [to_simple_order(o) for o in orders]}
            print(json.dumps(output))
        else:
            print(json.dumps(result))
            
    except Exception as e:
        print(f"DEBUG: main() 异常 - {type(e).__name__}: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        print(json.dumps({"error": str(e)}))


if __name__ == "__main__":
    main()