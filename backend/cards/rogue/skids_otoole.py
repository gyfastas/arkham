"""Skids O'Toole — Rogue Investigator.
能力：在你的回合中，花费2资源：你在本回合可以执行1个额外行动。（每回合限制1次。）
远古印记：+2。如果此次检定成功，获得2资源。

实现说明：
- 主动能力为自由触发能力，实现为 activate_extra_action() 公开方法
  （参考 the_necronomicon 的 activate 模式），由 UI 在其回合中调用。
- 通过 INVESTIGATOR_TURN_BEGINS / INVESTIGATOR_TURN_ENDS 跟踪当前回合调查员，
  保证"你的回合中"的限制；每回合限1次在回合开始时重置。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import ChaosTokenType, GameEvent, TimingPriority


class SkidsOToole(CardImplementation):
    card_id = "skids_otoole"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._used_this_turn = False
        self._current_turn_investigator: str | None = None
        self._elder_sign_pending = False

    def _get_skids(self, game_state, investigator_id):
        """Return the investigator state iff it is Skids O'Toole."""
        if investigator_id is None:
            return None
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return None
        card_data = getattr(inv, "card_data", None)
        if card_data is None or card_data.id != "skids_otoole":
            return None
        return inv

    @on_event(GameEvent.INVESTIGATOR_TURN_BEGINS, priority=TimingPriority.WHEN)
    def on_turn_begins(self, ctx):
        """跟踪当前回合调查员；Skids 的回合开始时重置限次。"""
        self._current_turn_investigator = ctx.investigator_id
        if self._get_skids(ctx.game_state, ctx.investigator_id) is not None:
            self._used_this_turn = False

    @on_event(GameEvent.INVESTIGATOR_TURN_ENDS, priority=TimingPriority.WHEN)
    def on_turn_ends(self, ctx):
        if self._current_turn_investigator == ctx.investigator_id:
            self._current_turn_investigator = None

    def activate_extra_action(self, game_state, investigator_id) -> bool:
        """主动能力：花费2资源获得1个额外行动（每回合限1次，仅限自己回合）。

        由 UI 在玩家选择发动时调用。
        """
        inv = self._get_skids(game_state, investigator_id)
        if inv is None:
            return False
        if self._used_this_turn:
            return False
        if self._current_turn_investigator != investigator_id:
            return False
        if inv.resources < 2:
            return False

        inv.resources -= 2
        inv.actions_remaining += 1
        self._used_this_turn = True
        return True

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.WHEN)
    def elder_sign_effect(self, ctx):
        """远古印记：+2。如果此次检定成功，获得2资源。"""
        if ctx.chaos_token != ChaosTokenType.ELDER_SIGN:
            return
        inv = self._get_skids(ctx.game_state, ctx.investigator_id)
        if inv is None:
            return
        ctx.modify_amount(2, "skids_otoole_elder_sign")
        self._elder_sign_pending = True

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.AFTER)
    def elder_sign_gain_resources(self, ctx):
        """远古印记检定成功：获得2资源。"""
        if not self._elder_sign_pending:
            return
        self._elder_sign_pending = False
        inv = self._get_skids(ctx.game_state, ctx.investigator_id)
        if inv is None:
            return
        inv.resources += 2

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear_elder_sign_pending(self, ctx):
        self._elder_sign_pending = False
