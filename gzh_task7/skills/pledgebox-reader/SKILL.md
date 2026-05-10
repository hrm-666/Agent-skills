---
name: pledgebox-reader
description: 查询PledgeBox众筹平台的订单、支持者和物流信息。当用户询问订单列表、支持者数据、按邮箱查找订单、订单状态统计、导出调查数据或任何PledgeBox数据查询时使用。
---

# PledgeBox数据读取技能

## 命令列表

列出订单
    python skills/pledgebox-reader/scripts/fetch_orders.py --list --page 1

按状态筛选（Locked/Unlock/Shipped）
    python skills/pledgebox-reader/scripts/fetch_orders.py --list --status Locked

按邮箱查找
    python skills/pledgebox-reader/scripts/fetch_orders.py --list --email "demo@pledgebox.com"

获取统计
    python skills/pledgebox-reader/scripts/fetch_orders.py --stats

导出JSON
    python skills/pledgebox-reader/scripts/fetch_orders.py --export-json orders.json

导出CSV
    python skills/pledgebox-reader/scripts/fetch_orders.py --export-csv orders.csv

## 输出格式

列表查询返回 total_count 和 orders 数组，展示时列出订单信息。

统计返回 total_orders、total_paid_amount、status_breakdown。

导出命令返回 success、message 和 file 路径，展示时告知用户保存位置。

## 示例

用户: "查看PledgeBox订单列表"

执行: python skills/pledgebox-reader/scripts/fetch_orders.py --list --page 1

用户: "导出订单为CSV"

执行: python skills/pledgebox-reader/scripts/fetch_orders.py --export-csv orders.csv