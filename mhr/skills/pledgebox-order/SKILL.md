---
name: pledgebox-order
description: 获取 PledgeBox 订单并清洗成统一 JSON 输出。当用户提到获取订单、拉取 PledgeBox 订单、导出订单数据、查询某个邮箱或某个 pb_id 的订单时使用。
---

# PledgeBox Order Skill

这个 skill 用于从 PledgeBox OpenAPI 获取订单数据，并按统一 JSON 格式导出结果。

## 适用场景

- 获取 PledgeBox 订单
- 查询指定邮箱的订单
- 查询指定 PledgeBox ID 的订单
- 导出原始订单和清洗后的订单 JSON

## 必填参数

- `api_token`
- `project_id`

## 可选参数

- `page`
- `all_pages`
- `is_completed`
- `order_status`
- `pb_id`
- `email`
- `output_dir`

## 接口说明

获取订单接口：

    GET https://api.pledgebox.com/api/openapi/orders

支持的订单状态：

    unlock / lock / shipped / refunded

## 执行流程

1. 运行 `scripts/fetch_orders.py` 请求 PledgeBox API。
2. 将原始响应保存到输出目录下的 `raw_orders.json`。
3. 运行 `scripts/clean_orders.py` 清洗订单字段。
4. 将清洗结果保存到 `cleaned_orders.json`。
5. 将失败记录保存到 `error_log.json`。

## 规则

- 不要在日志或回复里暴露完整 `api_token`
- 原始 API 响应必须完整保存，不要原地修改
- 缺失字段填 `null`
- `items`、`addons`、`gifts` 必须始终输出为数组
- 默认将输出写到 `workspace/pledgebox-order-output/`
- 最终输出应符合 `schema/cleaned_order_schema.json`
- 如果用户需要全量订单，优先添加 `--all_pages`

## 推荐命令

拉取已完成订单：

    bash: python skills/pledgebox-order/scripts/run_pipeline.py --api_token "YOUR_API_TOKEN" --project_id 100001 --is_completed 1

拉取全量分页订单：

    bash: python skills/pledgebox-order/scripts/run_pipeline.py --api_token "YOUR_API_TOKEN" --project_id 100001 --is_completed 1 --all_pages

拉取某个状态的订单：

    bash: python skills/pledgebox-order/scripts/run_pipeline.py --api_token "YOUR_API_TOKEN" --project_id 100001 --order_status shipped

查询某个邮箱：

    bash: python skills/pledgebox-order/scripts/run_pipeline.py --api_token "YOUR_API_TOKEN" --project_id 100001 --email demo@example.com

查询某个 PledgeBox ID：

    bash: python skills/pledgebox-order/scripts/run_pipeline.py --api_token "YOUR_API_TOKEN" --project_id 100001 --pb_id PBID001891441

## 返回给用户时的重点

- 获取到的原始订单数
- 清洗成功数
- 清洗失败数
- 输出文件路径
