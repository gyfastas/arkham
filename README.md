# Arkham Horror LCG - 复刻项目

基于 [ArkhamDB](https://zh.arkhamdb.com/search) 的卡牌游戏复刻项目。

## 目标

- 复刻 Arkham Horror: The Card Game 的核心卡牌和调查员
- 创作自定义剧本 (Homebrew Scenarios)
- 数据驱动：所有卡牌/调查员/剧本以 JSON 格式存储

---

## 快速启动

### 方式一：Phaser 客户端 + Socket.IO 服务端（推荐）

```bash
# 1. 构建前端（首次或前端有改动时执行）
cd client && npm install && npm run build && cd ..

# 2. 启动游戏服务（Socket.IO + 静态文件一体）
python3 server/main.py --port 8910

# 3. 打开浏览器
open http://localhost:8910
```

> 服务端同时托管 Socket.IO 和 Phaser 前端，只需启动一个进程。

#### 开发模式（前端热更新）

```bash
# Terminal 1：后端
python3 server/main.py --port 8910

# Terminal 2：Vite 开发服务器（自动代理 Socket.IO）
cd client && npm run dev
open http://localhost:5173
```

---

### 方式二：传统 HTML 前端（旧版，仍可用）

```bash
# 黛西·沃克关卡（失落知识的图书馆）
python3 frontend/server_daisy.py        # → http://localhost:8909

# 完整场景（夜幕降临）
python3 frontend/server_full.py         # → http://localhost:8908

# 简单战斗测试
python3 frontend/server.py              # → http://localhost:8907
```

---

### 运行测试

```bash
python3 -m pytest backend/tests/ -v    # 333 tests
python3 -m pytest backend/tests/ -q    # 简洁输出
```

---

## 当前进度

### 引擎核心（backend/）
- 技能检定完整流程（ST.1–ST.8）：提交卡牌、混沌袋抽取、结果判定
- 混沌袋：标准标记 + 调查员专属远古印记效果
- 伤害系统：生命/理智分配、盟友伤害吸收、借机攻击
- 敌人阶段：猎人移动、非猎人待机、交战/闪避
- 刷新阶段：横置卡牌恢复、资源补充、手牌补充
- 多幕场景：AgendaCard/ActCard 分支推进、多结局 Resolution
- 调查员模型：InvestigatorCard（经验/创伤/构筑要求）

### 卡牌数据（data/）
- **105 张**核心玩家卡牌（守卫者/探求者/流浪者/潜修者/求生者/中立）
- **5 位**调查员：罗兰·班克斯、黛西·沃克、老无赖、阿格尼丝·贝克、温蒂·亚当斯
- **3 个**官方剧本：夜幕降临 / 午夜假面 / 吞噬星辰

### 新版 Phaser 客户端（client/ + server/）
- **Socket.IO 实时通信**：服务端主动推送，无轮询
- **Phaser 3 + TypeScript**：游戏场景渲染（地图/手牌/敌人/日志）
- **动画系统**：混沌标记飞出、检定结果闪光、伤害浮字、敌人碎裂等 12 种动画
- **交互系统**：
  - 卡牌悬停 tooltip（名称/类型/费用/图标/效果文本）
  - 拖拽打出手牌
  - 检定前弹出**投入卡牌**面板（按技能类型筛选）
  - 武器选择 / 敌人选择 Modal
  - 弃牌堆浏览（点击查看全部弃牌）
- **房间/大厅系统**：创建房间 → 选择调查员和剧本 → 开始游戏
- **弃牌堆**：事件卡打出后入弃牌、技能卡提交后入弃牌、资产击败后入弃牌，客户端可查阅

### 测试
- **333 tests passed**（含研究图书馆员搜索消息、黛西 tome 行动修复）

---

## 项目结构

```
arkham/
├── backend/
│   ├── models/            # 数据模型 (state, investigator, scenario, chaos)
│   ├── engine/            # 游戏引擎 (phases, skill_test, damage, actions)
│   ├── cards/             # 卡牌实现 ({class}/*.py)
│   └── tests/             # 333 tests passed
├── server/                # Socket.IO 游戏服务端
│   ├── main.py            # 入口：aiohttp + Socket.IO，托管静态文件
│   ├── game_session.py    # 游戏会话，包装 backend 引擎
│   ├── room.py            # 房间/大厅管理
│   ├── state_serializer.py# 状态序列化（供新旧服务共用）
│   ├── event_logger.py    # 捕获可动画化事件
│   ├── player.py          # 玩家会话
│   └── protocol.py        # Socket.IO 消息类型定义
├── client/                # Phaser 3 + TypeScript 客户端
│   ├── src/
│   │   ├── scenes/        # Boot / Lobby / Game / GameOver
│   │   ├── objects/       # AnimationManager
│   │   ├── ui/            # Modal / Tooltip / SkillCommitModal
│   │   ├── network/       # SocketClient / Protocol
│   │   └── state/         # GameStore / types
│   ├── package.json
│   └── vite.config.ts     # 开发代理: /socket.io → :8910
├── frontend/              # 旧版 HTML 前端（仍可用）
│   ├── server_daisy.py    # 黛西测试关卡 (port 8909)
│   ├── server_full.py     # 完整场景测试 (port 8908)
│   └── server_core.py     # 旧版 HTTP 服务（复用 state_serializer）
├── data/
│   ├── investigators/     # 调查员 JSON
│   ├── player_cards/      # 玩家卡牌（支援/事件/技能）
│   ├── encounter_cards/   # 遭遇卡（敌人/诡计/地点）
│   ├── scenarios/         # 剧本
│   └── campaigns/         # 战役
├── dev_logs/              # 开发日志
├── skills/                # Agent skills
└── docs/                  # 设计文档与规则参考
```

---

## Roadmap

### ✅ 已完成
- **Phase 0**：状态序列化提取（`server/state_serializer.py`，供新旧服务共用）
- **Phase 1**：Socket.IO 游戏服务端（房间系统、实时推送、EventLogger）
- **Phase 2**：Phaser 3 核心渲染（4 个场景、完整 HUD、地图、手牌、敌人）
- **Phase 3**：动画与交互（12 种动画、拖拽、投入卡牌、Tooltip、弃牌堆查看）

### 🚧 进行中
- **Phase 4**：多人游戏（回合制执行、信息隔离、多调查员 HUD）

### 📋 计划中
- **Phase 5**：打磨与迁移（牌组构建器、3 个剧本端到端验证、响应式缩放）

---

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
- **事件 (Event)** — 一次性效果
- **技能 (Skill)** — 检定时提交的加值卡
- **敌人 (Enemy)** — 遭遇牌组中的怪物
- **诡计 (Treachery)** — 遭遇牌组中的负面效果
- **地点 (Location)** — 场景地图节点

## 数据来源

- https://zh.arkhamdb.com — 卡牌数据库（中文）
- https://arkhamdb.com — 卡牌数据库（英文）
- https://arkhamdb.com/api/ — API
