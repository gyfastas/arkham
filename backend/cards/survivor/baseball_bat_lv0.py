"""Baseball Bat (Level 0) — Survivor Asset, Hand x2.
[action]: Fight. You get +2 [combat] for this attack. This attack deals +1 damage.
If a [skull] or [auto_fail] symbol is revealed during this attack, discard
Baseball Bat after the attack resolves.
"""

from backend.cards.base import CardImplementation, on_event
from backend.engine.slots import vacate_asset_slots
from backend.models.enums import ChaosTokenType, GameEvent, Skill, TimingPriority

_BAD_TOKENS = {ChaosTokenType.SKULL, ChaosTokenType.AUTO_FAIL}


class BaseballBat(CardImplementation):
    card_id = "baseball_bat_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._discard_pending = False

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def combat_bonus(self, ctx):
        """使用球棒的攻击：+2 战斗。"""
        if ctx.skill_type != Skill.COMBAT:
            return
        if ctx.source != self.instance_id:
            return
        ctx.modify_amount(2, "baseball_bat_combat_bonus")

    @on_event(GameEvent.DAMAGE_DEALT, priority=TimingPriority.WHEN)
    def bonus_damage(self, ctx):
        """使用球棒的攻击：+1 伤害。"""
        if ctx.source != self.instance_id:
            return
        ctx.modify_amount(1, "baseball_bat_bonus_damage")

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.AFTER)
    def mark_bad_token(self, ctx):
        """本次攻击揭示了骷髅或自动失败标记：标记待弃置。"""
        if ctx.source != self.instance_id:
            return
        if ctx.chaos_token in _BAD_TOKENS:
            self._discard_pending = True

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def discard_after_attack(self, ctx):
        """攻击结算后弃置球棒。"""
        if not self._discard_pending:
            return
        self._discard_pending = False
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        vacate_asset_slots(ctx.game_state, self.instance_id)
        inv.play_area.remove(self.instance_id)
        ctx.game_state.cards_in_play.pop(self.instance_id, None)
        inv.discard.append("baseball_bat_lv0")
        ctx.extra["baseball_bat_discarded"] = True
        ctx.game_state.log_effect("🏏 球棒：揭示了骷髅/自动失败标记，攻击后弃置")
