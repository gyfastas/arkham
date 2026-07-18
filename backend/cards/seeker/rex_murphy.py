"""Rex Murphy — Seeker Investigator.
能力：[reaction]在调查时技能检定成功后，如果你超过难度至少2点：发现所在地点1个线索。
（每回合限1次。）
远古印记：+2。你可以选择让这次检定自动失败，来抽取3张卡牌。

简化说明：
- "调查时"通过 INVESTIGATE_ACTION_INITIATED 事件跟踪（SKILL_TEST_ENDS 清除）。
- 远古印记的"选择自动失败"采用预授权模式：UI/测试先调用 choose_autofail()，
  下一次远古印记结算时抽3张牌并以 -1000 修正近似自动失败
  （引擎无自动失败通道；难度0的检定在引擎中强制自动成功，无法被失败）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import ChaosTokenType, GameEvent, TimingPriority


class RexMurphy(CardImplementation):
    card_id = "rex_murphy"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._used_this_turn = False
        self._investigating: str | None = None
        self._autofail_armed = False

    def _get_rex(self, game_state, investigator_id):
        """Return the investigator state iff it is Rex Murphy."""
        if investigator_id is None:
            return None
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return None
        card_data = getattr(inv, "card_data", None)
        if card_data is None or card_data.id != "rex_murphy":
            return None
        return inv

    @on_event(GameEvent.ROUND_BEGINS, priority=TimingPriority.WHEN)
    def reset_turn_limit(self, ctx):
        """每轮开始时重置限次（Taboo errata：Limit once per round.）。"""
        self._used_this_turn = False

    @on_event(GameEvent.INVESTIGATE_ACTION_INITIATED, priority=TimingPriority.AFTER)
    def track_investigate(self, ctx):
        """标记接下来的技能检定为调查。"""
        self._investigating = ctx.investigator_id

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear_test_state(self, ctx):
        self._investigating = None
        self._autofail_armed = False

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.REACTION)
    def discover_clue_on_big_success(self, ctx):
        """[reaction]调查检定成功2点以上后：发现所在地点1个线索（每回合限1次）。"""
        if self._used_this_turn:
            return
        if self._investigating != ctx.investigator_id:
            return
        inv = self._get_rex(ctx.game_state, ctx.investigator_id)
        if inv is None:
            return

        margin = (ctx.modified_skill or 0) - (ctx.difficulty or 0)
        if margin < 2:
            return

        location = ctx.game_state.get_location(inv.location_id)
        if location is None or location.clues <= 0:
            return

        location.clues -= 1
        inv.clues += 1
        self._used_this_turn = True

    def choose_autofail(self, game_state, investigator_id) -> bool:
        """预授权：下一次远古印记结算时选择自动失败以抽3张牌。由 UI 调用。"""
        if self._get_rex(game_state, investigator_id) is None:
            return False
        self._autofail_armed = True
        return True

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.WHEN)
    def elder_sign_effect(self, ctx):
        """远古印记：+2；若已预授权，则改为抽3张牌并令本次检定（近似）自动失败。"""
        if ctx.chaos_token != ChaosTokenType.ELDER_SIGN:
            return
        inv = self._get_rex(ctx.game_state, ctx.investigator_id)
        if inv is None:
            return

        if self._autofail_armed:
            self._autofail_armed = False
            for _ in range(3):
                if inv.deck:
                    inv.hand.append(inv.deck.pop(0))
            ctx.modify_amount(-1000, "rex_murphy_elder_autofail")
            ctx.extra["rex_murphy_chose_autofail"] = True
        else:
            ctx.modify_amount(2, "rex_murphy_elder_sign")
