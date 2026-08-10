"""Ritual Candles (Level 0) — Mystic Asset, Hand slot. (02029)
[reaction] 在你进行的一次检定中揭示[skull]、[cultist]、[tablet]或[elder_thing]
标记后：本次检定你获得+1技能值。（多张仪式蜡烛可叠加——每个实例独立触发。）
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import ChaosTokenType, GameEvent, TimingPriority

_CANDLE_TOKENS = {
    ChaosTokenType.SKULL, ChaosTokenType.CULTIST,
    ChaosTokenType.TABLET, ChaosTokenType.ELDER_THING,
}


class RitualCandles(CardImplementation):
    card_id = "ritual_candles_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._triggered = False

    def _controls(self, ctx) -> bool:
        """仅当控制者就是正在检定的调查员（"a test you are performing"）。"""
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        return inv is not None and self.instance_id in inv.play_area

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.AFTER)
    def track_symbol(self, ctx):
        if ctx.chaos_token in _CANDLE_TOKENS and self._controls(ctx):
            self._triggered = True

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def skill_bonus(self, ctx):
        """命中四符号标记后：本次检定+1技能值。"""
        if not self._triggered or not self._controls(ctx):
            return
        ctx.modify_amount(1, "ritual_candles_bonus")

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._triggered = False
