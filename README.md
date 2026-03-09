# Arkham Horror LCG - 复刻项目

基于 [ArkhamDB](https://zh.arkhamdb.com/search) 的卡牌游戏复刻项目。

## 目标

- 复刻 Arkham Horror: The Card Game 的核心卡牌和调查员
- 创作自定义剧本 (Homebrew Scenarios)
- 数据驱动：所有卡牌/调查员/剧本以 JSON 格式存储

## 当前进度

- 105张核心玩家卡牌已注册 (6阵营)
- 引擎核心: 技能检定(ST.1-ST.8)、混沌袋、伤害分配(含盟友吸收)、借机攻击、敌人阶段(猎人移动)
- 模型: InvestigatorCard (经验/创伤/构筑要求)、多幕 AgendaCard/ActCard (分支推进)
- 前端测试关卡: 黛西·沃克「失落知识的图书馆」(port 8909)
- 322 测试通过

## Roadmap

### Phase 1: Server-Client 分离 (多人游戏基础)

当前 server_daisy.py / server_full.py 将游戏逻辑、状态序列化、HTTP 路由混写在单文件中。需要拆分为独立的 GameServer + 前端 Client，为后续多人游戏打基础。

**目标架构:**

```
┌─────────┐  WebSocket   ┌──────────────┐
│ Client  │ ◄──────────► │  GameServer  │
│ (HTML)  │   JSON msg   │  (Python)    │
└─────────┘              └──────┬───────┘
                                │
┌─────────┐  WebSocket   ┌──────┴───────┐
│ Client  │ ◄──────────► │  Game Engine │
│ (HTML)  │              │  (backend/)  │
└─────────┘              └──────────────┘
```

**关键变更:**
1. **GameServer 类** — 管理房间/会话、玩家连接、回合调度
2. **WebSocket 协议** — 替代 HTTP REST，支持服务端主动推送 (敌人阶段、遭遇卡、其他玩家行动)
3. **玩家身份与回合管理** — 多调查员轮流行动，共享游戏状态
4. **状态同步** — 每个玩家只看到自己的手牌，共享场面信息
5. **前端重构** — 通用 client.html 连接任意 GameServer，不再硬编码剧本

### Phase 2: 官方剧本导入与测试

从 ArkhamDB 导入官方剧本数据，用引擎运行完整流程并编写测试。

**目标剧本:**
1. **夜幕降临 (The Gathering)** — 核心包第1个剧本，3幕事件 + 3幕密谋，验证基础流程
2. **午夜假面 (The Midnight Masks)** — 核心包第2个剧本，多目标 + 时间压力
3. **吞噬星辰 (The Devourer Below)** — 核心包第3个剧本，Boss战 + 多结局分支

**每个剧本需要:**
- 遭遇卡组 JSON 数据 (敌人 + 诡计 + 地点)
- 密谋/事件卡数据 (AgendaCard/ActCard 实例化)
- 地图拓扑 (地点连接关系)
- 特殊规则实现 (剧本专属事件处理)
- 集成测试: 模拟完整游戏流程 (setup → 多轮 → 胜利/失败)
- 前端关卡页面

## 项目结构

```
arkham/
├── backend/
│   ├── models/            # 数据模型 (state, investigator, scenario, chaos)
│   ├── engine/            # 游戏引擎 (phases, skill_test, damage, actions)
│   ├── cards/             # 卡牌实现 ({class}/*.py)
│   └── tests/             # 测试 (322 passed)
├── frontend/
│   ├── server_daisy.py    # 黛西测试关卡 (port 8909)
│   ├── server_full.py     # 完整场景测试 (port 8908)
│   └── daisy.html         # 黛西前端页面
├── data/
│   ├── investigators/     # 调查员 JSON 数据
│   ├── player_cards/      # 玩家卡牌 (支援/事件/技能)
│   ├── encounter_cards/   # 遭遇卡牌 (敌人/诡计/地点)
│   ├── scenarios/         # 剧本
│   └── campaigns/         # 战役 (多剧本串联)
├── dev_logs/              # 开发日志
├── skills/                # Agent skills (绑定 .claude/skills)
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
