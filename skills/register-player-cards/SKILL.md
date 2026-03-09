# Register Player Cards

注册新的玩家卡牌到 Arkham Horror LCG 后端引擎。

## 触发词
- "register card" / "注册卡牌"
- "add player card" / "添加玩家卡"
- "new card" / "新卡"

## 流程

当用户提供卡牌信息时，按以下步骤完成注册：

### Step 1: 收集卡牌信息

向用户确认以下字段（必填标 *）：

| 字段 | 说明 | 示例 |
|------|------|------|
| id* | 小写英文+下划线+等级 | `machete_lv0` |
| name* | 英文名 | `Machete` |
| name_cn* | 中文名 | `弯刀` |
| class* | 阵营 | guardian/seeker/rogue/mystic/survivor/neutral |
| type* | 卡牌类型 | asset/event/skill |
| cost* | 资源费用 (技能卡为null) | `3` |
| level | 经验等级 0-5 | `0` |
| traits | 特征标签 | `["item", "weapon", "melee"]` |
| skill_icons | 技能图标 | `{"combat": 1}` |
| slots | 栏位 (仅支援) | `["hand"]` |
| text* | 效果文本 | 完整的卡牌效果描述 |
| health/sanity | 生命/理智 (仅支援) | `3` / `2` |
| keywords | 关键词 | `["fast"]` |
| uses | 使用次数 | `{"ammo": 4}` |
| unique | 是否唯一 | `true/false` |
| pack | 所属扩展 | `core` |

### Step 2: 生成三个文件

#### 2a. 卡牌数据 JSON
路径: `data/player_cards/{class}/{card_id}.json`
- 验证字段符合 `data/player_cards/schema.json`

#### 2b. 卡牌实现模块
路径: `backend/cards/{class}/{card_id}.py`
- 继承 `CardImplementation`
- 使用 `@on_event` 装饰器绑定效果到游戏事件
- 根据卡牌效果文本确定需要绑定的事件类型

**常见效果到事件映射：**

| 效果类型 | GameEvent | 说明 |
|----------|-----------|------|
| 战斗加成 | `SKILL_VALUE_DETERMINED` | 检查 skill_type == COMBAT |
| 调查加成 | `SKILL_VALUE_DETERMINED` | 检查 skill_type == INTELLECT |
| 额外伤害 | `DAMAGE_DEALT` | 修改 ctx.amount |
| 获取资源 | `CARD_PLAYED` | 事件卡打出时 |
| 成功抽牌 | `SKILL_TEST_SUCCESSFUL` | 检定成功后 |
| 进场效果 | `CARD_ENTERS_PLAY` | 卡牌进场时 |
| 离场效果 | `CARD_LEAVES_PLAY` | 卡牌离场时 |
| 受伤反应 | `DAMAGE_ASSIGNED` | 受到伤害时 |
| 击败反应 | `ENEMY_DEFEATED` | 敌人被击败时 |

**TimingPriority 选择：**
- `WHEN` — 中断效果，修改数值（如+伤害、+技能值）
- `FORCED` — 强制能力
- `AFTER` — 后续效果（如抽牌、获取资源）
- `REACTION` — 反应能力（可选触发）

#### 2c. 单元测试
路径: `backend/tests/test_cards/test_{card_id}.py`
- 测试卡牌注册成功
- 测试核心效果生效
- 测试边界条件（如无弹药、多敌人等）

### Step 3: 运行验证

```bash
# 运行该卡牌的测试
python3 -m pytest backend/tests/test_cards/test_{card_id}.py -v

# 运行完整性检查
python3 skills/register-player-cards/scripts/validate_card.py data/player_cards/{class}/{card_id}.json
```

### Step 4: 确认通过

所有测试通过后，向用户确认卡牌已成功注册。

## 参考

- 规则文档: `docs/rules/`
- 数据 Schema: `data/player_cards/schema.json`
- 已有卡牌实现: `backend/cards/` (guardian/seeker/neutral 各有示例)
- 五张参考卡牌: Machete, Magnifying Glass, Emergency Cache, Guts, .45 Automatic

## 示例卡牌实现模式

### 支援卡 (Asset) — 持续加成
```python
class MyWeapon(CardImplementation):
    card_id = "my_weapon_lv0"

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def combat_bonus(self, ctx):
        if ctx.source != self.instance_id:
            return
        if ctx.skill_type == Skill.COMBAT:
            ctx.modify_amount(1, "my_weapon_bonus")
```

### 事件卡 (Event) — 打出即生效
```python
class MyEvent(CardImplementation):
    card_id = "my_event_lv0"

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.AFTER)
    def resolve_effect(self, ctx):
        if ctx.extra.get("card_id") != "my_event_lv0":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv:
            inv.resources += 2
```

### 技能卡 (Skill) — 提交到检定
```python
class MySkill(CardImplementation):
    card_id = "my_skill_lv0"

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.AFTER)
    def on_success(self, ctx):
        if "my_skill_lv0" not in ctx.committed_cards:
            return
        # 检定成功后效果
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv and inv.deck:
            inv.hand.append(inv.deck.pop(0))
```
