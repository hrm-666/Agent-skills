---
name: bilibili-rank
description: 获取B站视频排行榜数据。当用户询问B站排行榜、热门视频、播放量最高、排名最高、鬼畜区、音乐区、游戏区等分区排行榜时，使用此技能。自动识别分区并获取数据，无需询问用户。
---

# B站排行榜技能

此技能从B站公开API获取排行榜数据，支持全站和指定分区。

## 分区代码

- 全站: 0
- 动画: 1
- 音乐: 3
- 游戏: 4
- 娱乐: 5
- 科技: 36
- 生活: 160
- 鬼畜: 119
- 时尚: 155
- 影视: 181

## 使用方法

获取全站排行榜：

    python skills/bilibili-rank/scripts/fetch_rank.py 10

获取指定分区排行榜：

    python skills/bilibili-rank/scripts/fetch_rank.py 119 5

脚本返回 JSON 格式的排行榜数据。

## 智能处理

- 如果用户提到具体分区名称（如鬼畜区、音乐区），自动使用对应的 rid
- 默认返回 top 10，用户可指定数量

## 示例

用户: "鬼畜区播放量最高的5个视频"

自动执行: python skills/bilibili-rank/scripts/fetch_rank.py 119 5

回复: 展示排行榜表格，然后询问用户是否需要保存数据

用户: "B站音乐区排行榜"

自动执行: python skills/bilibili-rank/scripts/fetch_rank.py 3 10

回复: 展示排行榜表格，然后询问用户是否需要保存数据