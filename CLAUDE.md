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

## 开发流程

- 默认工作分支：`dev`（日常开发都在 dev 上进行，push 到 origin/dev）
- `main` 仅用于稳定里程碑合并
- Commit 作者：YF <303887111@qq.com>（仓库级 git config）

## 战役模式与难度

- **混乱袋**：`data/chaos_bags.json`（官方组成：Easy 15 / Standard 16 / Hard 17 / Expert 18；敦威治用 elder_thing 替换 tablet）。
- **符号效果按难度**：token 效果取剧本参考卡对应面（Easy/Standard=正面，Hard/Expert=背面 `back_text`），游戏内参考卡文本同步按难度展示。遗留简化：选择类效果自动取常用分支、Brood 线索/技能卡图标无效化等个别机制未实现（代码内有注释）。
- **战役存档**：默认 `saves/campaigns/{save_id}.json`（已 gitignore），记录章节、牌组、XP、创伤、难度。存档目录可在开始界面「选项」中修改（设置存于 `saves/settings.json`）。
- **幕间结算**：游戏结束自动结算（victory 经验 + 被击败创伤），`campaign_upgrade` 服务端按牌组 diff 计价（升级=等级差 min1，新卡=等级 min1，移除免费）。
- **前端路由**：`/` 开始界面，`/quick` 快速游戏，`/campaign` 战役大厅，`/game`，`/gameover`（战役结算+升级+下一章）。
- **冒烟测试**：`python3 scripts/smoke_campaign.py`（需服务器运行中）。

## 开发原则

1. **检查实现逻辑**：改动先读透现有代码路径（引擎事件流 → 场景 → 序列化 → 前端），改动后必须跑测试验证，不凭感觉交付。
2. **与官方 DB 规则对齐**：卡牌/机制/数值以 ArkhamDB 卡面原文（含正反面、各难度分档）和官方 FAQ 为准，数据文件的翻译文本不作依据。
3. **确保功能一致性**：同一规则在引擎逻辑、UI 展示、接口返回、存档/结算中必须表现一致；玩家选择的配置（如难度）要贯穿到所有受影响的系统。

官方来源：
- ArkhamDB 卡面原文：https://arkhamdb.com （中文：https://zh.arkhamdb.com ，API：`/api/public/card/{code}` 含 `back_text`）
- 官方 FAQ / Taboo List：https://images-cdn.fantasyflightgames.com/filer_public/c1/d0/c1d0fab6-7fa6-4ce2-af6a-16416381a19b/ahc_faq_v25_february_2026-web.pdf
- 官方 Rules Reference：https://arkham606.com/rules
