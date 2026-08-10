"""Skeptic (Level 1) — Rogue Skill. (07115)
这次技能检定中，将每个[bless]和[curse]标记的修正值改为视为+1。

简化说明：
- 投入后本次检定揭示的祝福（原+2）/诅咒（原-2）标记修正值在
  CHAOS_TOKEN_RESOLVED 统一改为+1（引擎单标记揭示流程）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import ChaosTokenType, GameEvent, TimingPriority


class Skeptic(CardImplementation):
    card_id = "skeptic_lv1"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._armed = False

    @on_event(GameEvent.SKILL_TEST_COMMIT, priority=TimingPriority.WHEN)
    def arm(self, ctx):
        if self.card_id in ctx.committed_cards:
            self._armed = True

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.WHEN)
    def flatten_token_modifier(self, ctx):
        """祝福/诅咒标记的修正值视为+1。"""
        if not self._armed:
            return
        if ctx.chaos_token not in (ChaosTokenType.BLESS, ChaosTokenType.CURSE):
            return
        delta = 1 - (ctx.amount or 0)
        if delta:
            ctx.modify_amount(delta, "skeptic_flatten")
        ctx.extra["skeptic_applied"] = True
        ctx.game_state.log_effect("🤨 怀疑论者：祝福/诅咒标记修正值视为+1")

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._armed = False
