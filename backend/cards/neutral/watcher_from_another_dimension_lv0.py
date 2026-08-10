"""Watcher from Another Dimension (Level 0) — Neutral Enemy, Weakness.
祸害。隐私。猎手。
显现 - 秘密地将本敌人加入你的手牌。
只要本敌人在你手牌中，你可以攻击或躲避它（如同其在你所在地点）。如果
你成功，将其从你的手牌中丢弃。如果你失败，将其生成并与你交战。
强制 - 在你的牌堆耗尽时，如果本敌人在你手牌中：其（从你的手牌中）攻击你。

官方数值（arkhamdb 06017，玩家卡 JSON 通道不含 enemy_* 字段，需会话/数据
层接线；测试以 make_enemy_data 注入）：战斗5 / 生命2 / 躲避5 / 伤害3 / 恐惧0。

简化说明：
- 显现效果即"加入手牌"：抽到时不做额外结算（persistent_in_hand=True 保持
  手牌中的注册，供会话层查询/调用）。
- 手牌中的攻击/躲避没有引擎检定通道（敌人不在场上），由会话层发起检定后
  调用 resolve_success()（从手牌丢弃）或 resolve_failure()（生成并交战）。
- "牌堆耗尽"没有引擎事件（actions._draw 在牌堆空时洗弃牌堆+1恐惧，无
  DECK_EMPTY 钩子）：on_deck_empty() 供会话层在该分支调用，从手牌攻击
  持有者（伤害/恐惧读敌人卡数据，缺省按官方 3伤害/0恐惧）。
- 祸害（抽牌时不投入）/隐私（不对其他玩家展示）/猎手关键词依赖会话与
  敌人 AI 通道，引擎缺口。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority
from backend.models.state import CardInstance


class WatcherFromAnotherDimension(CardImplementation):
    card_id = "watcher_from_another_dimension_lv0"
    persistent_in_hand = True  # 手牌中持续可攻击/躲避

    @on_event(GameEvent.CARD_DRAWN, priority=TimingPriority.WHEN)
    def revelation(self, ctx):
        """显现 - 秘密地加入手牌（牌已入手，仅记录日志）。"""
        if ctx.extra.get("card_id") != "watcher_from_another_dimension_lv0":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or "watcher_from_another_dimension_lv0" not in inv.hand:
            return
        ctx.game_state.log_effect("👁️ 异次元监视者：秘密地加入手牌")
        ctx.extra["watcher_added_to_hand"] = True

    def resolve_success(self, game_state, investigator_id) -> bool:
        """手牌中的攻击/躲避成功：将其从手牌中丢弃。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or "watcher_from_another_dimension_lv0" not in inv.hand:
            return False
        inv.hand.remove("watcher_from_another_dimension_lv0")
        inv.discard.append("watcher_from_another_dimension_lv0")
        game_state.log_effect("👁️ 异次元监视者：检定成功，从手牌丢弃")
        return True

    def resolve_failure(self, game_state, investigator_id) -> str | None:
        """手牌中的攻击/躲避失败：生成并与你交战。返回敌人实例 id。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or "watcher_from_another_dimension_lv0" not in inv.hand:
            return None
        inv.hand.remove("watcher_from_another_dimension_lv0")
        inst_id = game_state.next_instance_id()
        enemy = CardInstance(
            instance_id=inst_id,
            card_id="watcher_from_another_dimension_lv0",
            owner_id=investigator_id,
            controller_id="scenario",
        )
        game_state.cards_in_play[inst_id] = enemy
        inv.threat_area.append(inst_id)
        game_state.log_effect("👁️ 异次元监视者：检定失败，生成并与你交战")
        return inst_id

    def on_deck_empty(self, game_state, investigator_id) -> bool:
        """强制 - 牌堆耗尽时本敌人在手牌中：其从手牌中攻击你。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or "watcher_from_another_dimension_lv0" not in inv.hand:
            return False
        cd = game_state.get_card_data("watcher_from_another_dimension_lv0")
        damage = getattr(cd, "enemy_damage", None) if cd is not None else None
        horror = getattr(cd, "enemy_horror", None) if cd is not None else None
        # 玩家卡 JSON 通道不含 enemy_* 字段：缺省按官方 3伤害/0恐惧
        inv.damage += damage if damage is not None else 3
        inv.horror += horror if horror is not None else 0
        game_state.log_effect("👁️ 异次元监视者：牌堆耗尽，从手牌中攻击你")
        return True
