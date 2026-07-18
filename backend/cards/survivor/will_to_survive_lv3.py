"""Will to Survive (Level 3) — Survivor Event.
快速。在你回合开始时打出。直到本回合结束，你所有技能+1。

简化说明：
- 中文卡面"每有一个已揭示的混沌标记+1"语义不通（与官方卡面不符），
  简化为本回合内所有技能检定 +1。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class WillToSurvive(CardImplementation):
    card_id = "will_to_survive_lv3"

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def activate_effect(self, ctx):
        if ctx.extra.get("card_id") != "will_to_survive_lv3":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if not hasattr(inv, "active_effects"):
            inv.active_effects = {}
        inv.active_effects["will_to_survive"] = True

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def all_skills_bonus(self, ctx):
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if not getattr(inv, "active_effects", {}).get("will_to_survive"):
            return
        ctx.modify_amount(1, "will_to_survive_bonus")

    @on_event(GameEvent.INVESTIGATOR_TURN_ENDS, priority=TimingPriority.AFTER)
    def expire(self, ctx):
        for inv in ctx.game_state.investigators.values():
            if hasattr(inv, "active_effects"):
                inv.active_effects.pop("will_to_survive", None)
