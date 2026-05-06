# PledgeBox Order Download - 第一阶段完成说明

## 第一阶段目标

本阶段完成海外众筹订单确认平台的数据获取能力：输入 PledgeBox API token 和 project_id，调用订单接口下载订单数据，保存原始 JSON，并按关系拆分为多个 CSV 表格，供后续清洗和目标物流/电商系统模板转换使用。

当前阶段只做数据下载和初步结构化，不做最终发货模板。

## 已完成能力

- 调用 `GET https://api.pledgebox.com/api/openapi/orders` 获取订单数据。
- 支持分页下载，通过 `page` 参数自动翻页。
- 默认只下载已完成 Survey 且已锁定的订单：`is_completed=1`，`order_status=lock`。
- 保存完整原始订单 JSON，方便后续回溯和重新清洗。
- 将嵌套订单数据拆成多个 CSV，而不是揉成一张大表。
- 输出运行摘要和异常记录。
- API token 不写死在代码中，支持环境变量和命令行参数。

## 使用方法

在 `D:\Agent\Agent-skills` 目录运行。

推荐用环境变量传 token：

```powershell
$env:PLEDGEBOX_API_TOKEN="你的token"
python skills/pledgebox-order-download/scripts/download_orders.py --project-id 100001
```

也可以直接通过命令行参数传 token：

```powershell
python skills/pledgebox-order-download/scripts/download_orders.py `
  --project-id 100001 `
  --api-token "你的token"
```

完整参数示例：

```powershell
python skills/pledgebox-order-download/scripts/download_orders.py `
  --project-id 100001 `
  --api-token "你的token" `
  --is-completed 1 `
  --order-status lock `
  --output-dir "workspace/pledgebox_exports" `
  --max-pages 100
```

## 输出文件

默认输出目录：

```text
workspace/pledgebox_exports/<project_id>/
```

输出内容：

- `raw_orders_<project_id>.json`：API 返回的完整原始订单数据。
- `orders_<project_id>.csv`：订单主表，一行一个订单，包含订单状态、邮箱、金额、收件地址等字段。
- `order_items_<project_id>.csv`：商品明细表，一行一个商品，展开 `reward.items`、`addons`、`gifts`。
- `questions_<project_id>.csv`：问卷表，一行一个问题答案，展开 reward、item、addon 级别的 questions。
- `run_summary_<project_id>.csv`：运行摘要，包含项目 ID、下载页数、订单数量、商品数量、问卷数量和输出路径。
- `errors_<project_id>.csv`：异常记录，包含 API 请求失败、返回结构异常、订单结构异常等信息。

## 安全说明

- 不要把真实 API token 写入代码。
- 不要把真实订单数据上传到公共仓库。
- 真实订单可能包含姓名、邮箱、电话、地址等个人信息，导出文件只应保存在本地受控目录。

## 当前限制

本阶段不处理以下内容：

- 地址智能纠错。
- 邮编、州、城市匹配校验。
- 香港、台湾等特殊地区地址规则。
- 报关金额处理。
- 商品套餐合并。
- 备注转商品记录。
- 目标物流/电商系统导入模板生成。

## 后续第二阶段

第二阶段可以基于本阶段输出的 `raw_orders`、`orders`、`order_items`、`questions` 做数据清洗、字段映射和目标系统模板生成。
