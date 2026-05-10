#!/usr/bin/env python3
"""
从 PledgeBox OpenAPI 获取订单数据
用法: python fetch_orders.py [--email XX] [--status XX] [--stats] [--list] [--raw] [--export-json FILE] [--export-csv FILE]
"""

import sys
import json
import csv
import argparse
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path
from typing import Dict, List, Optional


# ============================================================
# 1. API 读取层 - 返回原始数据
# ============================================================

def load_config() -> Dict:
    """从 config.yaml 或 .env 加载 PledgeBox 配置"""
    config = {
        "api_token": None,
        "project_id": None,
        "base_url": "https://api.pledgebox.com/api/openapi"
    }
    
    # 尝试从 config.yaml 读取
    config_yaml_path = Path(__file__).parent.parent.parent.parent / "config.yaml"
    if config_yaml_path.exists():
        try:
            import yaml
            with open(config_yaml_path, 'r', encoding='utf-8') as f:
                yaml_config = yaml.safe_load(f)
                if yaml_config and 'pledgebox' in yaml_config:
                    pb_config = yaml_config['pledgebox']
                    config['api_token'] = pb_config.get('api_token')
                    config['project_id'] = pb_config.get('project_id')
                    config['base_url'] = pb_config.get('api_base_url', config['base_url'])
        except ImportError:
            pass
        except Exception:
            pass
    
    # 尝试从 .env 文件读取
    env_path = Path(__file__).parent.parent.parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding='utf-8').splitlines():
            if line.startswith("PLEDGEBOX_API_TOKEN="):
                config['api_token'] = line.split("=", 1)[1].strip().strip('"').strip("'")
            elif line.startswith("PLEDGEBOX_PROJECT_ID="):
                config['project_id'] = line.split("=", 1)[1].strip().strip('"').strip("'")
    
    return config


def api_request(endpoint: str, params: Dict = None) -> Dict:
    """
    调用 PledgeBox API，返回原始响应
    返回格式与 PDF 一致: {"code": 200, "data": [...], "total_count": N}
    """
    config = load_config()
    
    if not config['api_token'] or not config['project_id']:
        return {
            "code": 401,
            "message": "API token 或 project_id 未配置，请在 .env 或 config.yaml 中设置",
            "data": [],
            "total_count": 0
        }
    
    # 构建请求参数
    url_params = {
        "api_token": config['api_token'],
        "project_id": config['project_id'],
        **(params or {})
    }
    
    url = f"{config['base_url']}/{endpoint}?{urllib.parse.urlencode(url_params)}"
    
    try:
        req = urllib.request.Request(url, method="GET")
        req.add_header("Accept", "application/json")
        
        with urllib.request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode('utf-8'))
            return data
            
    except urllib.error.HTTPError as e:
        return {"code": e.code, "message": e.reason, "data": [], "total_count": 0}
    except json.JSONDecodeError:
        return {"code": 500, "message": "响应解析失败", "data": [], "total_count": 0}
    except Exception as e:
        return {"code": 500, "message": str(e), "data": [], "total_count": 0}


def get_orders(
    page: int = 1,
    is_completed: Optional[int] = None,
    email: Optional[str] = None,
    pbid: Optional[str] = None,
    order_status: Optional[str] = None
) -> Dict:
    """获取订单数据，参数直接映射到 API"""
    params = {"page": page}
    if is_completed is not None:
        params["is_completed"] = is_completed
    if email:
        params["email"] = email
    if pbid:
        params["pb_id"] = pbid
    if order_status:
        params["order_status"] = order_status
    
    return api_request("orders", params)


# ============================================================
# 2. 格式转换层 - 将原始数据转换为各种格式
# ============================================================

def to_simple_order(order: Dict) -> Dict:
    """将单个订单转换为精简格式（便于 LLM 阅读）"""
    reward = order.get("reward", {})
    shipping = order.get("shipping_address", {})
    
    return {
        "pbid": order.get("pbid"),
        "email": order.get("email"),
        "order_status": order.get("order_status"),
        "survey_status": order.get("survey_status"),
        "paid_amount": order.get("paid_amount"),
        "balance": order.get("balance"),
        "date_confirmed": order.get("date_confirmed"),
        "reward_name": reward.get("name") if reward else None,
        "addons_count": len(order.get("addons", [])),
        "tracking_code": order.get("tracking_code"),
        "shipping_country": shipping.get("country"),
        "backer_name": shipping.get("name")
    }


def to_simple_list(orders: List[Dict]) -> List[Dict]:
    """批量转换为精简格式"""
    return [to_simple_order(o) for o in orders]


def to_csv_rows(orders: List[Dict]) -> List[Dict]:
    """转换为 CSV 友好的扁平结构"""
    rows = []
    for order in orders:
        shipping = order.get("shipping_address", {})
        reward = order.get("reward", {})
        
        row = {
            "id": order.get("id"),
            "pbid": order.get("pbid"),
            "email": order.get("email"),
            "order_status": order.get("order_status"),
            "survey_status": order.get("survey_status"),
            "paid_amount": order.get("paid_amount"),
            "balance": order.get("balance"),
            "credit_offer": order.get("credit_offer"),
            "date_confirmed": order.get("date_confirmed"),
            "tracking_code": order.get("tracking_code"),
            "shipping_country": shipping.get("country"),
            "shipping_city": shipping.get("city"),
            "shipping_state": shipping.get("state"),
            "backer_name": shipping.get("name"),
            "reward_name": reward.get("name") if reward else None,
            "addons_count": len(order.get("addons", [])),
            "note": order.get("note")
        }
        rows.append(row)
    return rows


def calculate_statistics(orders: List[Dict]) -> Dict:
    """计算统计数据"""
    if not orders:
        return {"error": "无数据"}
    
    total_orders = len(orders)
    total_paid = 0.0
    total_balance = 0.0
    status_count = {}
    
    for order in orders:
        total_paid += float(order.get("paid_amount", 0))
        total_balance += float(order.get("balance", 0))
        
        status = order.get("order_status", "Unknown")
        status_count[status] = status_count.get(status, 0) + 1
    
    return {
        "total_orders": total_orders,
        "total_paid_amount": round(total_paid, 2),
        "total_balance": round(total_balance, 2),
        "average_paid": round(total_paid / total_orders, 2) if total_orders > 0 else 0,
        "status_breakdown": status_count
    }


# ============================================================
# 3. 文件存储层
# ============================================================

def save_json(data, filepath: str) -> Dict:
    """保存为 JSON 文件"""
    try:
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return {"success": True, "message": f"已保存到 {filepath}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def save_csv(rows: List[Dict], filepath: str) -> Dict:
    """保存为 CSV 文件"""
    if not rows:
        return {"success": False, "error": "无数据"}
    
    try:
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
        
        return {"success": True, "message": f"已保存到 {filepath}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ============================================================
# 4. 主入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(description='获取 PledgeBox 订单数据')
    
    # 查询参数
    parser.add_argument('--list', action='store_true', help='列出订单（精简格式）')
    parser.add_argument('--raw', action='store_true', help='输出原始 API 格式（与 PDF 一致）')
    parser.add_argument('--stats', action='store_true', help='显示统计信息')
    parser.add_argument('--email', type=str, help='按邮箱筛选')
    parser.add_argument('--pbid', type=str, help='按 PledgeBox ID 筛选')
    parser.add_argument('--status', type=str, help='按状态筛选 (unlock/locked/shipped/refunded)')
    parser.add_argument('--completed', action='store_true', help='只显示已完成订单')
    parser.add_argument('--page', type=int, default=1, help='页码 (默认: 1)')
    
    # 导出参数
    parser.add_argument('--export-json', type=str, help='导出为 JSON 文件')
    parser.add_argument('--export-csv', type=str, help='导出为 CSV 文件')
    
    args = parser.parse_args()
    
    # 构建 API 参数
    is_completed = 1 if args.completed else None
    
    # 调用 API
    result = get_orders(
        page=args.page,
        is_completed=is_completed,
        email=args.email,
        pbid=args.pbid,
        order_status=args.status
    )
    
    orders = result.get("data", [])
    
    # 导出 JSON（完整原始数据）
    if args.export_json:
        save_json(result, args.export_json)
        return
    
    # 导出 CSV（扁平化）
    if args.export_csv:
        csv_rows = to_csv_rows(orders)
        save_csv(csv_rows, args.export_csv)
        return
    
    # 输出统计
    if args.stats:
        stats = calculate_statistics(orders)
        print(json.dumps(stats, ensure_ascii=False, indent=2))
        return
    
    # 输出精简列表
    if args.list:
        simple_orders = to_simple_list(orders)
        output = {
            "total_count": result.get("total_count", len(orders)),
            "orders": simple_orders
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return
    
    # 默认输出原始格式（与 PDF 一致）
    if args.raw or not (args.list or args.stats):
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return


if __name__ == "__main__":
    main()