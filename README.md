# Arkham Horror LCG - 复刻项目

基于 [ArkhamDB](https://zh.arkhamdb.com/search) 的卡牌游戏复刻项目。

## 目标

- 复刻 Arkham Horror: The Card Game 的核心卡牌和调查员
- 创作自定义剧本 (Homebrew Scenarios)
- 数据驱动：所有卡牌/调查员/剧本以 JSON 格式存储

## 项目结构

```
arkham/
├── data/
│   ├── investigators/     # 调查员 JSON 数据
│   ├── player_cards/      # 玩家卡牌 (支援/事件/技能)
│   ├── encounter_cards/   # 遭遇卡牌 (敌人/诡计/地点)
│   ├── scenarios/         # 剧本
│   └── campaigns/         # 战役 (多剧本串联)
├── skills/                # Agent skills (绑定 .claude/skills)
├── assets/images/         # 卡面图片资源
└── docs/                  # 设计文档与规则参考
```

## 阵营 (Classes)

| 英文 | 中文 | 色系 |
|------|------|------|
| Guardian | 守卫者 | 🔵 蓝 |
| Seeker | 探求者 | 🟡 黄 |
| Rogue | 流浪者 | 🟢 绿 |
| Mystic | 潜修者 | 🟣 紫 |
| Survivor | 求生者 | 🔴 红 |
| Neutral | 中立 | ⚪ 灰 |

## 卡牌类型

- **调查员 (Investigator)** — 玩家角色
- **支援 (Asset)** — 持续生效的装备/盟友
- **事件 (Event)** — ���次性效果
- **技能 (Skill)** — 检定时提交的加值卡
- **敌人 (Enemy)** — 遭遇牌组中的怪物
- **诡计 (Treachery)** — 遭遇牌组中的负面效果
- **地点 (Location)** — 场景地图节点

## 数据来源

- https://zh.arkhamdb.com — 卡牌数据库 (中文)
- https://arkhamdb.com — 卡牌数据库 (英文)
