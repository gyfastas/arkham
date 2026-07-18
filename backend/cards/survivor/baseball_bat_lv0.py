"""Baseball Bat (Level 0) — Survivor Asset, Hand x2.
消耗球棒：攻击。你获得+2战斗，本次攻击造成+1伤害。
如果这次攻击揭示一个负面混沌标记，弃置球棒。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import ChaosTokenType, GameEvent, Skill, TimingPriority

_BAD_TOKENS = {
    ChaosTokenType.SKULL, ChaosTokenType.CULTIST,
    ChaosTokenType.TABLET, ChaosTokenType.ELDER_THING,
    ChaosTokenType.AUTO_FAIL,
}


class BaseballBat(CardImplementation):
    card_id = "baseball_bat_lv0"

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def combat_bonus(self, ctx):
        if ctx.skill_type != Skill.COMBAT:
            return
        if ctx.extra.get("weapon_card_id") != "baseball_bat_lv0":
            return
        ctx.modify_amount(2, "baseball_bat_combat_bonus")

    @on_event(GameEvent.DAMAGE_DEALT, priority=TimingPriority.WHEN)
    def bonus_damage(self, ctx):
        if ctx.source != self.instance_id:
            return
        ctx.modify_amount(1, "baseball_bat_bonus_damage")

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.AFTER)
    def discard_on_bad_token(self, ctx):
        """揭示负面标记：弃置球棒。"""
        if ctx.chaos_token not in _BAD_TOKENS:
            return
        if ctx.extra.get("weapon_card_id") != "baseball_bat_lv0" and ctx.source != self.instance_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        inv.play_area.remove(self.instance_id)
        ctx.game_state.cards_in_play.pop(self.instance_id, None)
        inv.discard.append("baseball_bat_lv0")
        ctx.extra["baseball_bat_discarded"] = True
