#!/usr/bin/env python3
"""
测试 fetch_orders.py 中的所有函数
不需要 API Key，使用模拟数据
"""

import json
import sys
from pathlib import Path

# 导入要测试的函数
try:
    from fetch_orders import (
        to_simple_order,
        to_simple_list,
        to_csv_rows,
        calculate_statistics,
        save_json,
        save_csv
    )
    print("✅ 成功导入 fetch_orders 函数")
except ImportError as e:
    print(f"❌ 导入失败: {e}")
    print("请确保 test_fetch_orders.py 和 fetch_orders.py 在同一目录")
    sys.exit(1)

# ============================================================
# 模拟数据
# ============================================================

MOCK_ORDERS = [
    {
        "id": 3315433,
        "pbid": "PBID003315433",
        "email": "demo@pledgebox.com",
        "order_status": "Locked",
        "survey_status": "Completed",
        "paid_amount": 214,
        "balance": 20,
        "date_confirmed": "2026-03-05 17:30:56",
        "tracking_code": None,
        "courier_name": None,
        "credit_offer": 0,
        "note": "Tile + GrowLight Shipped",
        "reward": {
            "id": 11964,
            "name": "SUPER EARLY BIRD - PRO",
            "price": "194.0"
        },
        "shipping_address": {
            "country": "United States",
            "city": "Los Angeles",
            "state": "CA",
            "name": "John Doe",
            "phone": "1234567890"
        },
        "addons": [
            {"id": 1, "name": "Extra Battery", "price": "29.00"}
        ]
    },
    {
        "id": 3538819,
        "pbid": "PBID003538819",
        "email": "backer2@example.com",
        "order_status": "Unlock",
        "survey_status": "Completed",
        "paid_amount": 0,
        "balance": 48.86,
        "date_confirmed": "2022-12-09 01:09:19",
        "tracking_code": "TRACK123456",
        "courier_name": "UPS",
        "credit_offer": 50,
        "note": "Shipped",
        "reward": {
            "id": 11962,
            "name": "No Reward",
            "price": "1.0"
        },
        "shipping_address": {
            "country": "Canada",
            "city": "Toronto",
            "state": "ON",
            "name": "Jane Smith",
            "phone": "9876543210"
        },
        "addons": []
    }
]

# ============================================================
# 测试函数（每个都有明确输出）
# ============================================================

def test_to_simple_order():
    """测试1: 单条订单精简转换"""
    print("\n[测试1] to_simple_order()")
    print("-" * 40)
    
    result = to_simple_order(MOCK_ORDERS[0])
    
    # 检查必填字段是否存在
    required = ["pbid", "email", "order_status", "paid_amount", "reward_name", "shipping_country"]
    missing = [f for f in required if f not in result]
    
    if missing:
        print(f"❌ 失败: 缺少字段 {missing}")
        return False
    
    # 检查字段值是否正确
    if result["pbid"] != "PBID003315433":
        print(f"❌ 失败: pbid 值错误，期望 PBID003315433，得到 {result['pbid']}")
        return False
    
    if result["email"] != "demo@pledgebox.com":
        print(f"❌ 失败: email 值错误")
        return False
    
    if result["order_status"] != "Locked":
        print(f"❌ 失败: order_status 值错误")
        return False
    
    if result["reward_name"] != "SUPER EARLY BIRD - PRO":
        print(f"❌ 失败: reward_name 值错误")
        return False
    
    print(f"✅ 通过")
    print(f"   输出: pbid={result['pbid']}, email={result['email']}, status={result['order_status']}, reward={result['reward_name']}")
    return True


def test_to_simple_list():
    """测试2: 批量精简转换"""
    print("\n[测试2] to_simple_list()")
    print("-" * 40)
    
    result = to_simple_list(MOCK_ORDERS)
    
    if len(result) != len(MOCK_ORDERS):
        print(f"❌ 失败: 数量不一致，期望 {len(MOCK_ORDERS)}，得到 {len(result)}")
        return False
    
    if len(result) != 2:
        print(f"❌ 失败: 应该返回 2 条数据")
        return False
    
    print(f"✅ 通过")
    print(f"   输入: {len(MOCK_ORDERS)} 条，输出: {len(result)} 条")
    return True


def test_to_csv_rows():
    """测试3: CSV 扁平化转换"""
    print("\n[测试3] to_csv_rows()")
    print("-" * 40)
    
    result = to_csv_rows(MOCK_ORDERS)
    
    if len(result) != len(MOCK_ORDERS):
        print(f"❌ 失败: 数量不一致")
        return False
    
    if len(result) != 2:
        print(f"❌ 失败: 应该返回 2 行")
        return False
    
    # 检查字段数量（至少要有10个字段）
    if len(result[0].keys()) < 10:
        print(f"❌ 失败: 字段太少，只有 {len(result[0].keys())} 个")
        return False
    
    # 检查关键字段
    expected_fields = ["pbid", "email", "order_status", "paid_amount", "shipping_country"]
    for field in expected_fields:
        if field not in result[0]:
            print(f"❌ 失败: 缺少字段 {field}")
            return False
    
    print(f"✅ 通过")
    print(f"   生成 {len(result)} 行，每行 {len(result[0].keys())} 个字段")
    return True


def test_calculate_statistics():
    """测试4: 统计计算"""
    print("\n[测试4] calculate_statistics()")
    print("-" * 40)
    
    result = calculate_statistics(MOCK_ORDERS)
    
    # 检查总订单数
    if result.get("total_orders") != 2:
        print(f"❌ 失败: total_orders 期望 2，得到 {result.get('total_orders')}")
        return False
    
    # 检查总付款金额 (214 + 0 = 214)
    if result.get("total_paid_amount") != 214:
        print(f"❌ 失败: total_paid_amount 期望 214，得到 {result.get('total_paid_amount')}")
        return False
    
    # 检查平均付款 (214 / 2 = 107)
    if result.get("average_paid") != 107.0:
        print(f"❌ 失败: average_paid 期望 107.0，得到 {result.get('average_paid')}")
        return False
    
    # 检查状态分布
    status = result.get("status_breakdown", {})
    if status.get("Locked") != 1 or status.get("Unlock") != 1:
        print(f"❌ 失败: status_breakdown 错误，得到 {status}")
        return False
    
    print(f"✅ 通过")
    print(f"   总订单: {result['total_orders']}, 总金额: {result['total_paid_amount']}, 平均: {result['average_paid']}")
    print(f"   状态分布: {result['status_breakdown']}")
    return True


def test_save_json():
    """测试5: JSON 文件保存"""
    print("\n[测试5] save_json()")
    print("-" * 40)
    
    test_file = "test_output.json"
    result = save_json(MOCK_ORDERS, test_file)
    
    if not result.get("success"):
        print(f"❌ 失败: {result.get('error')}")
        return False
    
    if not Path(test_file).exists():
        print(f"❌ 失败: 文件未创建")
        return False
    
    # 验证文件内容
    try:
        with open(test_file, 'r', encoding='utf-8') as f:
            loaded = json.load(f)
        if len(loaded) != len(MOCK_ORDERS):
            print(f"❌ 失败: 文件内容数量不一致")
            return False
    except Exception as e:
        print(f"❌ 失败: 无法读取文件 - {e}")
        return False
    
    # 清理
    Path(test_file).unlink()
    print(f"✅ 通过")
    print(f"   已保存 {len(MOCK_ORDERS)} 条数据到 {test_file}，验证后已删除")
    return True


def test_save_csv():
    """测试6: CSV 文件保存"""
    print("\n[测试6] save_csv()")
    print("-" * 40)
    
    csv_rows = to_csv_rows(MOCK_ORDERS)
    test_file = "test_output.csv"
    result = save_csv(csv_rows, test_file)
    
    if not result.get("success"):
        print(f"❌ 失败: {result.get('error')}")
        return False
    
    if not Path(test_file).exists():
        print(f"❌ 失败: 文件未创建")
        return False
    
    # 验证文件内容
    try:
        content = Path(test_file).read_text(encoding='utf-8-sig')
        lines = content.strip().split('\n')
        # 第一行是表头，所以数据行数 = lines - 1
        if len(lines) - 1 != len(MOCK_ORDERS):
            print(f"❌ 失败: CSV 行数不正确")
            return False
    except Exception as e:
        print(f"❌ 失败: 无法读取文件 - {e}")
        return False
    
    # 清理
    Path(test_file).unlink()
    print(f"✅ 通过")
    print(f"   已保存 {len(csv_rows)} 行数据到 {test_file}，验证后已删除")
    return True


def test_edge_cases():
    """测试7: 边界情况"""
    print("\n[测试7] 边界情况测试")
    print("-" * 40)
    
    # 测试空列表
    empty_result = to_simple_list([])
    if len(empty_result) != 0:
        print(f"❌ 失败: to_simple_list([]) 应该返回空列表")
        return False
    
    empty_stats = calculate_statistics([])
    if "error" not in empty_stats:
        print(f"❌ 失败: calculate_statistics([]) 应该返回 error")
        return False
    
    # 测试缺失字段的订单
    bad_order = {
        "pbid": "TEST001",
        "email": "test@test.com"
        # 缺少 reward、shipping_address
    }
    try:
        simple = to_simple_order(bad_order)
        if simple.get("reward_name") is not None:
            print(f"❌ 失败: 缺失 reward 时应该返回 None")
            return False
        if simple.get("shipping_country") is not None:
            print(f"❌ 失败: 缺失 shipping_address 时应该返回 None")
            return False
    except Exception as e:
        print(f"❌ 失败: 处理缺失字段时崩溃 - {e}")
        return False
    
    print(f"✅ 通过")
    print(f"   空列表处理正确，缺失字段处理正确")
    return True


# ============================================================
# 主入口
# ============================================================

def main():
    print("\n" + "="*50)
    print("fetch_orders.py 函数测试")
    print("="*50)
    
    tests = [
        ("to_simple_order", test_to_simple_order),
        ("to_simple_list", test_to_simple_list),
        ("to_csv_rows", test_to_csv_rows),
        ("calculate_statistics", test_calculate_statistics),
        ("save_json", test_save_json),
        ("save_csv", test_save_csv),
        ("edge_cases", test_edge_cases),
    ]
    
    passed = 0
    failed = 0
    results = []
    
    for name, test_func in tests:
        try:
            if test_func():
                passed += 1
                results.append((name, "✅ 通过"))
            else:
                failed += 1
                results.append((name, "❌ 失败"))
        except Exception as e:
            failed += 1
            results.append((name, f"❌ 异常: {e}"))
    
    print("\n" + "="*50)
    print("测试结果汇总")
    print("="*50)
    for name, status in results:
        print(f"  {status}")
    
    print("-"*50)
    print(f"  总计: {passed} 通过, {failed} 失败")
    print("="*50)
    
    if failed == 0:
        print("\n🎉 所有测试通过！代码可以正常使用。")
    else:
        print(f"\n⚠️ 有 {failed} 个测试失败，请检查代码。")
    
    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)