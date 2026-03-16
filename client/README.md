# Arkham Horror LCG

复刻 Arkham Horror: The Card Game 的网页版实现。

## 技术栈

- **后端**: Python (Socket.IO server + 游戏引擎)
- **前端**: Vue 3 + TypeScript + Vite
- **通信**: Socket.IO (WebSocket)

## 快速开始

```bash
# 后端
pip install -r requirements.txt
python server/main.py

# 前端
cd client
npm install
npm run dev
```

访问 http://localhost:5173

## 项目结构

```
backend/          # 游戏引擎 (Python)
  engine/         # 核心引擎 (Game, Action, SkillTest, Phase)
  models/         # 数据模型 (CardData, GameState, Scenario)
  scenarios/      # 剧本控制器
  cards/          # 卡牌效果实现
  tests/          # 测试 (pytest)
server/           # Socket.IO 服务端
  main.py         # 入口
  game_session.py # 游戏会话
  campaign.py     # 战役状态
client/           # Vue 3 前端
  src/views/      # 页面 (Lobby, Game, GameOver)
  src/components/ # 组件 (Card, DeckBuilder, etc.)
  src/stores/     # Pinia 状态管理
  src/network/    # Socket.IO 通信层
data/             # JSON 数据
  investigators/  # 调查员
  player_cards/   # 玩家卡牌
  encounter_cards/# 遭遇卡
  scenarios/      # 剧本定义
  campaigns/      # 战役定义
  preset_decks/   # 预设卡组
```

## 当前内容

- 核心包 5 调查员 + 敦威治遗产 5 调查员
- 核心包 3 剧本 + 敦威治遗产 8 剧本数据
- 完整卡组构筑系统 (等级限制 / 预设 / JSON导入)
- 战役经验 (XP) 系统
- 遭遇卡抽取与展示

## 数据来源

- [ArkhamDB 中文](https://zh.arkhamdb.com)
- [ArkhamDB API](https://arkhamdb.com/api/)

## 致谢

- [halogenandtoast/ArkhamHorror](https://github.com/halogenandtoast/ArkhamHorror) — 前端架构设计参考，感谢其开源的 Vue.js 实现和完善的游戏引擎设计
- [ArkhamDB](https://arkhamdb.com) — 卡牌数据和图片资源
- Fantasy Flight Games — Arkham Horror: The Card Game 原版桌游
