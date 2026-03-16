# 后端机制完善计划 — 对齐 halogenandtoast/ArkhamHorror

> 参考: https://github.com/halogenandtoast/ArkhamHorror (Vue 3 + Haskell 全栈)
> 日期: 2026-03-12
> 当前测试: 371 passed

---

## P1 — 关键结构性缺失（影响大部分卡牌正确运作）

### 1. Window / Timing 时机系统 [HIGH EFFORT]

**现状**: EventBus 只有事件触发+处理，无玩家响应窗口。`TimingPriority` 枚举（WHEN, FORCED, AFTER, REACTION）仅用于 handler 排序，不提供交互窗口。

**参考实现**: `Arkham.Window` 模块 ~50 种窗口类型（WhenEnemyAttacks, AfterEnemyEngaged, WhenWouldTakeDamage, AfterSkillTestEnds, FastPlayerWindow 等）。每个窗口是游戏暂停让玩家选择触发能力/打快速卡的时机点。

**实施方案**:
- 新建 `backend/engine/window.py`
  - `WindowType` 枚举: FAST_PLAYER_WINDOW, WHEN_ENEMY_ATTACKS, AFTER_SKILL_TEST, WHEN_WOULD_TAKE_DAMAGE, AFTER_ENEMY_ENGAGED, BEFORE_SKILL_TEST, WHEN_REVEAL_CHAOS_TOKEN 等
  - `Window` dataclass: type, timing (when/after), source, target
  - `WindowManager`: 在关键时机点暂停游戏，检查是否有可触发的能力/快速卡，若有则生成 pending_choice 让玩家决定
- 修改 `backend/engine/game.py` 在各阶段插入窗口检查点
- 修改 `backend/engine/skill_test.py` 在 ST 各步骤间插入窗口
- 快速卡可玩规则: 哪些窗口允许打 Fast 事件/支援
- When/After 触发区分 + 取消语义

**影响文件**:
- `backend/engine/window.py` (新建)
- `backend/engine/game.py` (修改)
- `backend/engine/skill_test.py` (修改)
- `backend/engine/actions.py` (修改 — 添加 Fast 卡打出逻辑)
- `backend/models/enums.py` (修改 — 添加 WindowType)

---

### 2. Modifier 修正系统 [HIGH EFFORT]

**现状**: 修正值通过 event handler 调用 `ctx.modify_amount()` ad-hoc 处理。无集中追踪、无持续时间管理、无法查询"当前影响此调查员的所有修正"。

**参考实现**: `Arkham.Modifier` ~100 种修正类型（SkillModifier, ShroudModifier, DamageDealt, HorrorDealt, ActionCostModifier, AdditionalActions, CannotInvestigate, CannotMove 等），按来源追踪，含持续时间（this phase/round/test, while in play）。

**实施方案**:
- 新建 `backend/engine/modifier.py`
  - `ModifierType` 枚举: SKILL_WILLPOWER, SKILL_INTELLECT, SKILL_COMBAT, SKILL_AGILITY, SHROUD, DAMAGE_DEALT, HORROR_DEALT, ACTION_COST, ADDITIONAL_ACTIONS, CANNOT_INVESTIGATE, CANNOT_MOVE, CANNOT_FIGHT, CANNOT_EVADE 等
  - `Modifier` dataclass: type, value, source (card_instance_id), duration (permanent/this_round/this_phase/this_test/while_in_play), condition (optional callable)
  - `ModifierStack`: 集中管理所有活跃修正，支持查询/过期/堆叠
- 修改技能检定流程读取 ModifierStack 计算最终技能值
- 修改 `InvestigatorState` 添加 `get_modified_skill(skill_type)` 方法
- 每回合/每阶段结束时清理过期修正

**影响文件**:
- `backend/engine/modifier.py` (新建)
- `backend/models/state.py` (修改 — InvestigatorState 添加修正查询)
- `backend/engine/skill_test.py` (修改 — 读取修正)
- `backend/engine/game.py` (修改 — 阶段结束清理)
- 各卡牌实现 (逐步迁移到 Modifier 系统)

---

### 3. 遭遇卡框架重构 [MEDIUM EFFORT]

**现状**: `ScenarioController.resolve_encounter_card()` 是巨型 if/elif 链。诡计状态存为 `scenario.vars["treacheries"]` 的 plain dict。Surge/Peril/Hidden 关键词无系统处理。

**参考实现**: Treachery/Enemy 作为一等实体，有自己的状态机（revealed side, attached state）和关键词系统。

**实施方案**:
- 新建 `backend/models/encounter.py`
  - `EncounterCard` 基类: id, name, type (enemy/treachery), keywords (surge/peril/hidden)
  - `TreacheryCard(EncounterCard)`: revelation_effect, forced_effect, attached_to, discard_condition
  - `EncounterEnemy(EncounterCard)`: spawn_rule, prey, keywords (aloof/massive/hunter/retaliate/alert)
- 新建 `backend/engine/encounter_resolver.py`
  - 统一的遭遇卡处理流程: 抽取 → 检查 Peril → 处理 Hidden → 触发 Revelation → 检查 Surge
  - 替代 ScenarioController 中的 if/elif 链
- 遭遇卡注册机制（类似玩家卡的 CardRegistry）

**影响文件**:
- `backend/models/encounter.py` (新建)
- `backend/engine/encounter_resolver.py` (新建)
- `backend/scenarios/official_core.py` (修改 — 迁移到新框架)
- `backend/models/enums.py` (修改 — 添加 EncounterKeyword)

---

## P2 — 重要机制缺失

### 4. 多人投入技能卡 [LOW EFFORT]

**现状**: `_st2_commit` 只接受测试者自己的卡。

**方案**: ST.2 步骤向同一地点的所有调查员提供投入窗口（依赖 Window 系统）。

**影响文件**: `backend/engine/skill_test.py`

---

### 5. 混沌标记符号解析 [LOW EFFORT]

**现状**: `_st4_resolve_token` 从 `CHAOS_TOKEN_VALUES` 读取，符号标记返回 `None`。

**方案**:
- 每个剧本定义符号标记解析函数: `skull_value(game, investigator) -> int`
- 调查员专属 Elder Sign 效果
- `ScenarioController` 注册标记解析钩子

**影响文件**:
- `backend/engine/skill_test.py` (修改)
- `backend/scenarios/official_core.py` (修改 — 添加符号定义)

---

### 6. 敌人生成规则 [MEDIUM EFFORT]

**现状**: 简单的"同地点则交战"。

**方案**:
- 敌人关键词: Aloof (不自动交战), Massive (与所有调查员交战), Prey (优先目标)
- 生成规则: spawn at specific location / farthest / most clues
- 添加到 `EncounterEnemy` 模型

**影响文件**:
- `backend/models/encounter.py` (同 P1.3)
- `backend/engine/actions.py` (修改 — 交战规则)
- `backend/engine/game.py` (修改 — 敌人阶段)

---

### 7. 结构化能力激活系统 [HIGH EFFORT]

**现状**: 各卡牌自己实现费用检查，无统一框架。只有 Daisy 的 `_tome_activate` 特殊处理。

**方案**:
- 新建 `backend/engine/ability.py`
  - `AbilityCost`: action, exhaust, spend_uses(n), spend_resources(n), discard_self
  - `AbilityLimit`: per_round, per_game, per_phase, group_limit
  - `Ability`: cost, limit, timing (action/fast/reaction/forced), effect, eligibility_check
- `ActionResolver` 添加通用 `_activate` handler
- 卡牌注册能力而非直接处理事件

**影响文件**:
- `backend/engine/ability.py` (新建)
- `backend/engine/actions.py` (修改)
- `backend/cards/` (逐步迁移)

---

### 8. 诡计生命周期 [MEDIUM EFFORT]

**现状**: 诡计存为 plain dict，无事件交互、无强制触发、无弃置条件。

**方案**: 合并到 P1.3 的遭遇卡框架，给诡计添加:
- 附着状态 (attached to location/investigator)
- 威胁区域 (threat area) 概念
- 强制效果 (forced triggers while in play)
- 弃置条件 (discard conditions)

**影响文件**: 同 P1.3

---

## P3 — 游戏完整性

### 9. 多人汇集线索推进事件卡 [LOW]
- `advance_act` 改为检查同地点所有调查员线索总和
- 文件: `backend/engine/game.py`

### 10. 调查员被击败后果 [LOW]
- 击败时: 掉落线索到当前地点、弃置所有卡牌、移除出场
- 区分 killed vs. driven insane (影响战役 trauma)
- 全员淘汰 → 游戏结束
- 文件: `backend/engine/game.py`, `backend/models/state.py`

### 11. 移动时自动交战 [LOW]
- 调查员移动到有未交战敌人的地点 → 自动交战
- 敌人阶段重新交战 ready 的未交战敌人
- 文件: `backend/engine/actions.py`, `backend/engine/game.py`

### 12. 卡牌离场清理 [LOW]
- 离场时: 移除标记/附着物、触发离场能力、通知 CardRegistry 注销 handler
- 文件: `backend/engine/actions.py`, `backend/cards/registry.py`

### 13. 胜利展示区追踪 [LOW]
- 击败有 Victory 关键词的敌人 → 移入 victory_display
- 影响 XP 计算
- 文件: `backend/engine/game.py`

### 14. Surge 关键词系统化 [LOW]
- 遭遇卡解析后检查 Surge → 再抽一张
- 文件: `backend/engine/encounter_resolver.py` (同 P1.3)

### 15. 弱点卡系统 [MEDIUM]
- 基础弱点 (游戏中抽到生效)
- 调查员专属弱点 (在牌组中)
- 不能正常弃置、部分永久存在
- 文件: `backend/engine/game.py`, `backend/models/state.py`

---

## P4 — 锦上添花

### 16. 地点翻面 [LOW]
- 进入未翻面地点 → 翻面 → 触发翻面效果

### 17. 卡牌上的 Doom [LOW]
- 卡牌自身放置 doom 的机制（如 Arcane Initiate）

### 18. 多重混沌标记抽取 [LOW]
- 部分卡牌揭示多个标记选一（如 Olive McBride）

### 19. 战役日志 [MEDIUM]
- 结构化日志条目、跨剧本检查、记录集

### 20. 多人规则 [MEDIUM]
- 遭遇卡抽取顺序、威胁区域目标、协助检定

---

## 实施顺序

```
Phase A (基础设施):
  A1. Modifier 系统 → backend/engine/modifier.py
  A2. Window/Timing 系统 → backend/engine/window.py
  A3. 结构化能力系统 → backend/engine/ability.py

Phase B (遭遇卡重构):
  B1. 遭遇卡框架 → backend/models/encounter.py + encounter_resolver.py
  B2. 诡计生命周期 (合并到 B1)
  B3. Surge/Peril/Hidden 关键词
  B4. 敌人生成规则 (Aloof/Massive/Prey)

Phase C (技能检定增强):
  C1. 符号标记剧本解析
  C2. 多人投入技能卡
  C3. Elder Sign 调查员效果

Phase D (游戏流程补全):
  D1. 移动时自动交战 + 敌人阶段重交战
  D2. 多人汇集线索推进
  D3. 调查员击败后果
  D4. 卡牌离场清理 + handler 注销
  D5. 胜利展示区追踪
  D6. 弱点卡系统

Phase E (内容扩展):
  E1. 迁移现有遭遇卡到新框架
  E2. 迁移现有卡牌到 Ability 系统
  E3. 地点翻面、Doom on cards、多重标记
  E4. 战役日志、多人规则
```

## 验证

```bash
# 每个 Phase 完成后
python3 -m pytest backend/tests/ -v
# 新增测试覆盖新系统
python3 -m pytest backend/tests/test_modifiers.py -v
python3 -m pytest backend/tests/test_windows.py -v
python3 -m pytest backend/tests/test_encounter_framework.py -v
```
