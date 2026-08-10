"""Fight or Flight (Level 0) — Survivor Event.
快速。只能在你回合中打出。
直到本轮结束，你获得+X战斗和+X敏捷，其中X等于你身上的恐惧数量。

简化说明：
- X 为动态值：每次战斗/敏捷检定按你当前身上的恐惧数量实时计算
  （官方为持续能力，恐惧变化后加值随之变化）。
- "只能在你回合打出"由出牌时机约束（引擎/UI），实现内不重复校验
  （同 will_to_survive 的既有处理）。
- 效果经 active_effects 标记持有，ROUND_ENDS 过期（本轮结束）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority

_EFFECT_KEY = "fight_or_flight_lv0"


class FightOrFlight(CardImplementation):
    card_id = "fight_or_flight_lv0"

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def activate_effect(self, ctx):
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if not hasattr(inv, "active_effects"):
            inv.active_effects = {}
        inv.active_effects[_EFFECT_KEY] = True
        ctx.game_state.log_effect(
            f"💪 战斗或逃跑：本轮内 +{inv.horror}战斗/+{inv.horror}敏捷"
            f"（按身上恐惧动态计算）")

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def skill_bonus(self, ctx):
        """战斗/敏捷检定 +X，X=你身上的恐惧数量。"""
        if ctx.skill_type not in (Skill.COMBAT, Skill.AGILITY):
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if not getattr(inv, "active_effects", {}).get(_EFFECT_KEY):
            return
        if inv.horror > 0:
            ctx.modify_amount(inv.horror, "fight_or_flight_horror_bonus")

    @on_event(GameEvent.ROUND_ENDS, priority=TimingPriority.AFTER)
    def expire(self, ctx):
        """本轮结束：效果过期。"""
        for inv in ctx.game_state.investigators.values():
            effects = getattr(inv, "active_effects", None)
            if effects:
                effects.pop(_EFFECT_KEY, None)
