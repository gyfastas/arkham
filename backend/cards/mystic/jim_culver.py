"""Jim Culver — Mystic Investigator.
能力：将你抽出的[骷髅]标记的修正值视为0。
每次你抽出[远古印记]标记时，你可以选择将其视为[骷髅]标记。
远古印记：+1。

简化说明：
- 引擎默认骷髅修正为0（CHAOS_TOKEN_VALUES[SKULL] 为 None），此实现作为守卫：
  无论场景或其他效果把骷髅修正改成多少，Jim 结算时一律压回 0。
- "将远古印记视为骷髅"采用预授权模式：UI/测试先调用 choose_skull_instead()，
  下一次远古印记结算时修正压回 0（不应用远古印记的 +1）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import ChaosTokenType, GameEvent, TimingPriority


class JimCulver(CardImplementation):
    card_id = "jim_culver"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._skull_instead_armed = False

    def _get_jim(self, game_state, investigator_id):
        """Return the investigator state iff it is Jim Culver."""
        if investigator_id is None:
            return None
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return None
        card_data = getattr(inv, "card_data", None)
        if card_data is None or card_data.id != "jim_culver":
            return None
        return inv

    def choose_skull_instead(self, game_state, investigator_id) -> bool:
        """预授权：下一次远古印记结算时将其视为骷髅标记（修正为0）。由 UI 调用。"""
        if self._get_jim(game_state, investigator_id) is None:
            return False
        self._skull_instead_armed = True
        return True

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.WHEN)
    def resolve_token(self, ctx):
        """骷髅视为0；远古印记 +1（或按预授权视为骷髅）。"""
        inv = self._get_jim(ctx.game_state, ctx.investigator_id)
        if inv is None:
            return

        if ctx.chaos_token == ChaosTokenType.SKULL:
            if ctx.amount != 0:
                ctx.modify_amount(-ctx.amount, "jim_culver_skull_as_zero")
            return

        if ctx.chaos_token == ChaosTokenType.ELDER_SIGN:
            if self._skull_instead_armed:
                self._skull_instead_armed = False
                if ctx.amount != 0:
                    ctx.modify_amount(-ctx.amount, "jim_culver_elder_sign_as_skull")
                ctx.extra["jim_culver_treated_as_skull"] = True
            else:
                ctx.modify_amount(1, "jim_culver_elder_sign")

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear_test_state(self, ctx):
        self._skull_instead_armed = False
