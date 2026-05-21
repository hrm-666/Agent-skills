---
name: pledgebox-order
description: 获取 PledgeBox 订单并清洗成统一 JSON 输出。当用户提到获取订单、拉取 PledgeBox 订单、导出订单数据、查询某个邮箱或某个 pb_id 的订单时使用。
---

# PledgeBox Order Skill

这个 skill 用于从 PledgeBox OpenAPI 获取订单数据，并使用当前网页端 agent 所选模型按固定字段结构完成清洗，然后导出 JSON 结果。

## 强制执行规则

- 只能执行仓库中已经存在的脚本：`skills/pledgebox-order/scripts/run_pipeline.py`
- 不要自己编写临时 Python 代码
- 不要自己用 `curl`
- 不要自己读取或写入 `workspace/raw_orders.json` 之类的临时文件来代替正式流程
- 不要猜测 `.kimi/skills/...`、`~/.skills/...` 或其他不存在的目录
- 不要拆成多个命令分别执行
- 激活本 skill 后，必须直接运行下面给出的唯一命令模板

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

1. 直接运行 `skills/pledgebox-order/scripts/run_pipeline.py`
2. 脚本内部会先拉取原始订单并保存 `raw_orders.json`
3. 脚本内部会逐条调用当前网页端 agent 所选模型完成清洗
4. 脚本内部会逐条写入 `cleaned_orders.json`
5. 脚本内部会逐条写入 `error_log.json`
6. 脚本内部会持续更新 `progress.json`

## 规则

- 不要在日志或回复里暴露完整 `api_token`
- 原始 API 响应必须完整保存，不要原地修改
- 缺失字段由 LLM 按字段结构约束补成 `null`
- `items`、`addons`、`gifts` 必须始终输出为数组
- 默认将输出写到 `workspace/pledgebox-order-output/`
- 最终输出应符合 `schema/cleaned_order_schema.json`
- 如果用户需要全量订单，优先添加 `--all_pages`
- 清洗禁止依赖样本硬编码规则，应由当前网页端 agent 所选模型进行字段分类

## 网页端使用方式

在网页端直接告诉 agent：

- 获取某个 `project_id` 的订单
- 是否只要已完成订单
- 是否要全量分页
- 是否按 `email` 或 `pb_id` 精确查询

## 唯一允许的命令模板

只允许按用户给出的参数拼接下面这一条命令：

    bash: python skills/pledgebox-order/scripts/run_pipeline.py --api_token "..." --project_id 123456

如果用户要求只拉已完成订单，则在同一条命令后追加：

    --is_completed 1

如果用户要求全量分页，则在同一条命令后追加：

    --all_pages

如果用户指定状态、邮箱或 pb_id，则只允许继续在同一条命令后追加对应参数：

    --order_status shipped
    --email demo@example.com
    --pb_id PBID001891441

## 禁止行为示例

以下做法全部不允许：

- `curl https://api.pledgebox.com/...`
- `python -c "..."`
- `cd workspace && python ...`
- `python3 workspace/clean_orders.py`
- `python .kimi/skills/pledgebox-order/...`
- 先 `fetch_orders.py` 再手写代码清洗

## 返回给用户时的重点

- 获取到的原始订单数
- 清洗成功数
- 清洗失败数
- 输出文件路径
