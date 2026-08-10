"""Narrow Escape (Level 0) — Rogue Event.
快速。在敌人对你进行趁乱攻击时打出。
取消该次攻击。本回合中你下一次技能检定+2技能值。

简化说明：
- 从手牌中自动触发：敌人对你造成趁乱攻击（ATTACK_OF_OPPORTUNITY）时，
  若手牌中有本卡则自动打出（费用0）并取消该次攻击
  （官方为玩家自行选择打出时机）。
- +2技能值通过 active_effects 武装，下一次技能检定生效后消耗，
  你的回合结束时过期。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority

_EFFECT_KEY = "narrow_escape_lv0"


class NarrowEscape(CardImplementation):
    card_id = "narrow_escape_lv0"
    persistent_in_hand = True  # 在手牌中持续监听趁乱攻击窗口

    @on_event(GameEvent.ATTACK_OF_OPPORTUNITY, priority=TimingPriority.WHEN)
    def cancel_aoo(self, ctx):
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.card_id not in inv.hand:
            return

        # 自动打出（简化：官方为玩家选择时机；费用0）
        cd = ctx.game_state.get_card_data(self.card_id)
        cost = (getattr(cd, "cost", 0) or 0) if cd else 0
        if inv.resources < cost:
            return
        inv.resources -= cost
        inv.hand.remove(self.card_id)
        inv.discard.append(self.card_id)

        ctx.cancel()
        if not hasattr(inv, "active_effects"):
            inv.active_effects = {}
        inv.active_effects[_EFFECT_KEY] = True
        ctx.extra["narrow_escape_cancelled"] = True
        ctx.game_state.log_effect("💨 死里逃生：取消趁乱攻击，下一次检定+2")

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def apply_boost(self, ctx):
        """本回合下一次技能检定+2技能值（一次性）。"""
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        effects = getattr(inv, "active_effects", {})
        if not effects.get(_EFFECT_KEY):
            return
        ctx.modify_amount(2, "narrow_escape_boost")
        effects.pop(_EFFECT_KEY, None)

    @on_event(GameEvent.INVESTIGATOR_TURN_ENDS, priority=TimingPriority.AFTER)
    def expire(self, ctx):
        """回合结束时未用的+2过期。"""
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        effects = getattr(inv, "active_effects", None)
        if effects:
            effects.pop(_EFFECT_KEY, None)
