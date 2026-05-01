---

name: pledgebox-sync
description: Synchronize unlocked and completed order data from the PledgeBox OpenAPI into a local MySQL database. The skill performs incremental synchronization using hash comparison to detect new or updated orders, ensures data consistency by rebuilding related item records, and validates shipping addresses based on country and ZIP/postal code rules. It is designed for order management, fulfillment workflows, and downstream logistics processing.

---

# PledgeBox 订单同步 Skill

## 一、功能概述

本 Skill 用于从 **PledgeBox OpenAPI** 同步订单数据到本地 MySQL 数据库。

### 数据来源

API 地址由以下环境变量动态构造：

```
https://api.pledgebox.com/api/openapi/orders
?api_token={PLEDGEBOX_API_TOKEN}
&project_id={PLEDGEBOX_PROJECT_ID}
&is_completed=1
```

| 参数 | 来源 | 说明 |
|------|------|------|
| `api_token` | `.env` 中的 `PLEDGEBOX_API_TOKEN` | API 认证令牌 |
| `project_id` | `.env` 中的 `PLEDGEBOX_PROJECT_ID` | 项目 ID |
| `is_completed` | 固定值 `1` | 仅同步已完成 Survey 的订单 |

同步范围：

```text id="scope"
is_completed = 1
```

即：**仅同步已完成 Survey 的订单**

### API 返回数据结构

```json
{
  "data": [...20条订单...],
  "total_count": 55,
  "code": 200
}
```

每条订单包含以下主要字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | int | PledgeBox 订单 ID |
| `pbid` | string | 订单唯一标识 (如 PBID003315433) |
| `order_status` | string | 订单状态 (Locked/Unlock/Shipped) |
| `survey_status` | string | Survey 状态 (Completed) |
| `email` | string | 买家邮箱 |
| `paid_amount` | decimal | 已付金额 |
| `credit_offer` | decimal | 信用额度 |
| `balance` | decimal | 余额 |
| `courier_name` | string | 快递公司 |
| `tracking_code` | string | 追踪号 |
| `shipping_address` | object | 收货地址（嵌套） |
| `reward` | object | 奖励商品（含 items/addons/gifts） |
| `addons` | array | 附加商品 |
| `gifts` | array | 赠品 |

### 数据→表映射关系

| API 字段 | → | 数据库表 | 字段 |
|----------|---|----------|------|
| `id`, `pbid`, `order_status`, `survey_status`, `email`, `paid_amount`, `credit_offer`, `balance`, `courier_name`, `tracking_code` | → | **orders** | id, pbid, order_status, survey_status, email, paid_amount, credit_offer, balance, courier_name, tracking_code |
| `shipping_address` (嵌套对象) | → | **order_addresses** | recipient_name, phone, address_line1, city, state, country, country_code, zip |
| `reward.items` | → | **order_items** | source_type='reward', product_id, name, sku, price, quantity |
| `addons` 数组 | → | **order_items** | source_type='addon', product_id, name, sku, price, quantity |
| `gifts` 数组 | → | **order_items** | source_type='gift', product_id, name, sku, price, quantity |
| `items[].variant` (嵌套对象) | → | **item_variants** | variant_key, variant_value |
| `items[].questions` (嵌套数组) | → | **item_questions** | question, answer |
| `shipping_address.country_code` + `zip` | → | **geo_reference** | 用于地址校验 |

### 同步流程

```
1. API 获取 (is_completed=1)
       ↓
2. 遍历每条订单
       ↓
3. ┌─────────────────────────────────────────┐
   │ 写入 orders 表（主表）                   │
   │ 写入 order_addresses 表（地址）         │
   │ 遍历 reward/items → order_items         │
   │ 遍历 addons → order_items               │
   │ 遍历 gifts → order_items                │
   │ 每条 item 的 variant → item_variants   │
   │ 每条 item 的 questions → item_questions │
   └─────────────────────────────────────────┘
       ↓
4. 计算 data_hash 用于增量判断
       ↓
5. 写入 MySQL 6 张表
```

---

## 二、配置说明

所有配置从 `.env` 文件自动读取，无需手动输入：

| 环境变量 | 说明 | 示例值 |
| -------- | ---- | ------ |
| `PLEDGEBOX_API_TOKEN` | PledgeBox API 令牌 | （已配置在 .env） |
| `PLEDGEBOX_PROJECT_ID` | 项目 ID | `100001` |
| `MYSQL_HOST` | 数据库主机 | `localhost` |
| `MYSQL_PORT` | 数据库端口 | `3306` |
| `MYSQL_USER` | 数据库用户名 | `root` |
| `MYSQL_PASSWORD` | 数据库密码 | （已配置在 .env） |
| `MYSQL_DATABASE` | 数据库名 | `pledgebox` |

---

## 三、核心能力

### 1. 自动初始化数据库

* 首次运行时： 自动检测数据库和表结构 → 不存在则自动创建 
* 支持部分表存在的情况（幂等执行）

### 2. 增量同步（核心）

* 使用 `pbid` 作为唯一标识
* 生成 `data_hash` 判断数据是否变化

| 情况  | 操作     |
| --- | ------ |
| 新订单 | INSERT |
| 已变更 | UPDATE |
| 未变化 | SKIP   |

---

### 3. 数据一致性

当订单发生变化时：

删除该订单所有子数据 → 全量重建

---

### 4. 地址校验（发货关键）

规则：

* 有邮编 → 使用 (country_code + zip) 校验
* 无邮编（如香港） → 默认有效

字段：

```text id="geo"
geo_status = valid / invalid
```

---

### 5. 商品结构支持

支持：

* 商品（items / addons / gifts）
* 变体（variant）
* 用户填写信息（questions）

---

### 6. 失效订单处理

未出现在本次同步中的订单：

```text id="inactive"
is_active = 0
```

---

### 7. 稳定性保障

* API 重试（3次）
* 限速（0.2秒）
* MySQL 分布式锁

### 8. 同步过程报告输出

每次执行同步后，会在项目 `workspace` 目录生成一份 Markdown 总结文件：

* 文件名：`pledgebox-sync-summary-YYYYMMDD-HHMMSS.md`
* 内容包含：
* API 拉取页数与订单数量
* 与 `uploads/orders_full.json` 的对比结果（新增/删除/变更/未变更）
* 数据库操作结果（insert/update/skip/deactivate/error）
* 失败时的错误与 traceback

---

## 四、数据库结构（6表）

| 表名 | 说明 | 关联 |
| ---- | ---- | ---- |
| `orders` | 订单主表 | - |
| `order_addresses` | 订单收货地址 | → orders.id |
| `order_items` | 订单商品明细 | → orders.id |
| `item_variants` | 商品变体属性 | → order_items.id |
| `item_questions` | 用户填写问题 | → order_items.id |
| `geo_reference` | 邮编地区参考表 | - |

### 表字段详情

#### orders（订单主表）

| 字段 | 类型 | 说明 |
| ---- | ---- | ---- |
| id | BIGINT | 主键 |
| pbid | VARCHAR(50) | PledgeBox 订单唯一标识 |
| order_status | VARCHAR(50) | 订单状态 |
| survey_status | VARCHAR(50) | Survey 完成状态 |
| email | VARCHAR(255) | 买家邮箱 |
| paid_amount | DECIMAL(10,2) | 已付金额 |
| credit_offer | DECIMAL(10,2) | 信用额度 |
| balance | DECIMAL(10,2) | 余额 |
| courier_name | VARCHAR(100) | 快递公司 |
| tracking_code | VARCHAR(100) | 追踪号 |
| data_hash | VARCHAR(64) | 数据指纹（用于增量判断） |
| is_active | TINYINT | 是否有效（1=有效，0=已失效） |
| last_synced_at | DATETIME | 最后同步时间 |

#### order_addresses（收货地址）

| 字段 | 类型 | 说明 |
| ---- | ---- | ---- |
| id | BIGINT | 主键 |
| order_id | BIGINT | 关联 orders.id |
| recipient_name | VARCHAR(255) | 收货人姓名 |
| phone | VARCHAR(50) | 联系电话 |
| address_line1 | VARCHAR(255) | 详细地址 |
| city | VARCHAR(100) | 城市 |
| state | VARCHAR(100) | 州/省 |
| country | VARCHAR(100) | 国家名称 |
| country_code | VARCHAR(10) | 国家代码（如 US、CN） |
| zip | VARCHAR(20) | 邮编 |
| geo_status | VARCHAR(20) | 地址校验结果（valid/invalid） |

#### order_items（订单商品）

| 字段 | 类型 | 说明 |
| ---- | ---- | ---- |
| id | BIGINT | 主键 |
| order_id | BIGINT | 关联 orders.id |
| source_type | VARCHAR(20) | 商品类型（item/addon/gift） |
| product_id | BIGINT | PledgeBox 商品 ID |
| name | VARCHAR(255) | 商品名称 |
| sku | VARCHAR(100) | 商品 SKU |
| price | DECIMAL(10,2) | 单价 |
| quantity | INT | 数量 |

#### item_variants（商品变体）

| 字段 | 类型 | 说明 |
| ---- | ---- | ---- |
| id | BIGINT | 主键 |
| item_id | BIGINT | 关联 order_items.id |
| variant_key | VARCHAR(100) | 变体属性名（如 Color、Size） |
| variant_value | VARCHAR(255) | 变体属性值（如 Red、M） |

#### item_questions（用户填写信息）

| 字段 | 类型 | 说明 |
| ---- | ---- | ---- |
| id | BIGINT | 主键 |
| item_id | BIGINT | 关联 order_items.id |
| question | TEXT | 问题内容 |
| answer | TEXT | 用户回答 |

#### geo_reference（邮编参考表）

| 字段 | 类型 | 说明 |
| ---- | ---- | ---- |
| id | BIGINT | 主键 |
| country_code | VARCHAR(10) | 国家代码 |
| zip | VARCHAR(20) | 邮编 |
| city | VARCHAR(100) | 城市 |
| state | VARCHAR(100) | 州/省 |

---

## 五、输出结果

```json id="output"
{
  "inserted": 10,
  "updated": 3,
  "skipped": 25,
  "deactivated": 5,
  "errors": 0
}
```

---

## 六、执行流程

1. 获取数据库锁
2. 分页拉取订单
3. 计算 hash
4. 判断增量
5. 写入数据库
6. 标记失效订单
7. 释放锁

---

## 七、用户触发示例（Prompts）

### 模糊触发（无需提及具体技术细节）

* 同步数据
* 同步一下
* 把最新订单同步到数据库
* 刷新订单数据
* 更新订单
* 同步订单
* 同步最新订单
* 把 PledgeBox 数据同步过来

### 明确触发

* 同步 PledgeBox 的订单到我的数据库
* 拉取最新的未锁定订单并更新本地 MySQL
* 帮我刷新订单数据，用 PledgeBox API 同步一下
* 更新所有已完成但未锁定的订单数据
* 把最新订单同步到数据库，用于发货

---

### English Examples

* Sync PledgeBox orders into my MySQL database
* Fetch latest unlocked completed orders and update local DB
* Refresh order data from PledgeBox API
* Update my database with the latest fulfillment-ready orders
* Sync order data for shipping and logistics processing
* Sync the data
* Sync latest
* Update orders

---

## 八、使用建议

* 建议每 5~15 分钟执行
* 发货前筛选：

```sql id="sql"
geo_status = 'valid'
```

---

## 九、注意事项

* API 无更新时间字段
* 使用 hash 判断变更
* variant / questions 结构不稳定，已做兼容处理
* 配置完全来自 `.env` 文件，首次运行前确保已配置
* 在本项目的 Windows shell 环境中，不要使用 `mysql -u$MYSQL_USER ...` 这类命令（`$VAR` 不会按预期展开）

---

## 十、数据库查询规范（重要）

当用户要求“看数据库里有什么 / 看表结构 / 查订单”时，必须使用 Python 查询脚本，不直接拼 `mysql` CLI 命令。

统一命令：

```bash
python skills/pledgebox-sync/scripts/query_db.py --show-tables
python skills/pledgebox-sync/scripts/query_db.py --describe orders
python skills/pledgebox-sync/scripts/query_db.py --sql "SELECT pbid, order_status, survey_status, last_synced_at FROM orders ORDER BY id DESC LIMIT 20;"
```

说明：

* 该脚本自动读取 `.env` 的 MySQL 连接信息
* 输出 JSON 结果，便于直接在对话中总结
* 若查询失败，返回具体错误信息，便于定位连接/权限/SQL 问题
* 不要向用户索要 MySQL 密码；默认使用项目 `.env` 既有配置直接执行查询

---
