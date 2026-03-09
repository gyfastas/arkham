# Arkham Horror LCG 复刻项目

## 项目概述

复刻 Arkham Horror: The Card Game，参考 https://zh.arkhamdb.com/search 构筑卡牌、调查员及自创剧本。

## 数据规范

- 所有卡牌/调查员/剧本数据以 JSON 格式存储于 `data/` 目录
- 每个数据子目录下有 `schema.json` 定义字段规范
- 卡牌ID命名: 小写英文+下划线，如 `roland_banks`, `machete_lv0`
- 中英双语：`name` (英文) + `name_cn` (中文) 必填

## 术语对照

| English | 中文 | 说明 |
|---------|------|------|
| Investigator | 调查员 | 玩家角色 |
| Guardian | 守卫者 | 蓝色阵营 |
| Seeker | 探求者 | 黄色阵营 |
| Rogue | 流浪者 | 绿色阵营 |
| Mystic | 潜修者 | 紫色阵营 |
| Survivor | 求生者 | 红色阵营 |
| Asset | 支援 | 持续生效卡 |
| Event | 事件 | 一次性卡 |
| Skill | 技能 | 检定加值卡 |
| Enemy | 敌人 | 遭遇组怪物 |
| Treachery | 诡计 | 遭遇组负面效果 |
| Location | 地点 | 场景地图节点 |
| Scenario | 剧本 | 单次游戏流程 |
| Campaign | 战役 | 多剧本串联 |
| Willpower | 意志 | 四维之一 |
| Intellect | 智力 | 四维之一 |
| Combat | 战斗 | 四维之一 |
| Agility | 敏捷 | 四维之一 |

## Skills 目录

`skills/` 目录存放 agent skills，与 `.claude/skills/` 绑定。
添加新 skill 时在 `skills/<name>/` 下创建，同步到 `.claude/skills/`。

## 数据来源

- ArkhamDB 中文: https://zh.arkhamdb.com
- ArkhamDB 英文: https://arkhamdb.com
- ArkhamDB API: https://arkhamdb.com/api/
