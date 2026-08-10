"""Recall the Future (Level 2) — Mystic Asset. (Augury, Ritual)
[reaction] 当你正在执行的技能检定开始时，如果回忆未来处于就绪状态，
指定1个混沌标记：如果本次检定中揭示了指定的混沌标记，横置回忆未来。
然后，本次检定你的技能值+2。

简化说明：
- 指定标记经公开方法 arm()（或由会话层传参），无选择 UI 时不自动指定。
- 命中后横置并在本次检定+2技能值（CHAOS_TOKEN_RESOLVED 置标，
  SKILL_VALUE_DETERMINED 结算加值）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import ChaosTokenType, GameEvent, TimingPriority


class RecallTheFuture(CardImplementation):
    card_id = "recall_the_future_lv2"
    activations = [{
        "id": "name_token",
        "label": "【反应】指定1个混沌标记：本次检定揭示则+2技能值",
        "method": "arm",
    }]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._named_token: ChaosTokenType | None = None
        self._hit = False

    def arm(self, game_state, investigator_id: str, token) -> bool:
        """【反应】指定1个混沌标记（须本卡就绪且在场上）。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None or inst.exhausted:
            return False
        if not isinstance(token, ChaosTokenType):
            try:
                token = ChaosTokenType(token)
            except ValueError:
                return False
        self._named_token = token
        self._hit = False
        return True

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.AFTER)
    def check_hit(self, ctx):
        if self._named_token is None or ctx.chaos_token != self._named_token:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None or inst.exhausted:
            return
        inst.exhausted = True
        self._hit = True
        ctx.extra["recall_the_future_hit"] = True

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def apply_boost(self, ctx):
        if not self._hit:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        ctx.modify_amount(2, "recall_the_future_boost")
        self._hit = False

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._named_token = None
        self._hit = False
