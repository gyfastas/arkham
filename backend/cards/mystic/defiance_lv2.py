"""Defiance (Level 2) — Mystic Skill. (04198)
忽略本次检定期间揭示的所有[skull]、[cultist]、[tablet]和[elder_thing]符号的
效果（包括其修正值）。

简化说明：
- 投入后（SKILL_TEST_COMMIT 见到本卡）武装；CHAOS_TOKEN_RESOLVED 时若标记
  为上述符号：清零其修正并将 ctx.chaos_token 置为 None，使后续（AFTER）
  的符号触发效果（如皱缩术受恐）不再响应。原标记记录在 ctx.extra。
- 不忽略[auto_fail]（卡面未列出）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import ChaosTokenType, GameEvent, TimingPriority

_IGNORED = {
    ChaosTokenType.SKULL, ChaosTokenType.CULTIST,
    ChaosTokenType.TABLET, ChaosTokenType.ELDER_THING,
}


class Defiance(CardImplementation):
    card_id = "defiance_lv2"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._active = False

    @on_event(GameEvent.SKILL_TEST_COMMIT, priority=TimingPriority.WHEN)
    def arm(self, ctx):
        if self.card_id in (ctx.committed_cards or []):
            self._active = True

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.WHEN)
    def ignore_symbol(self, ctx):
        """忽略符号标记的效果与修正值。"""
        if not self._active or ctx.chaos_token not in _IGNORED:
            return
        token = ctx.chaos_token
        if ctx.amount:
            ctx.modify_amount(-ctx.amount, "defiance_ignore")
        ctx.chaos_token = None
        ctx.extra["defiance_ignored"] = token.value
        ctx.game_state.log_effect(f"🛡️ 逆反：忽略[{token.value}]的效果与修正")

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._active = False
