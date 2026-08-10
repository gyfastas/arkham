"""Father Mateo — Mystic Investigator.
能力：[reaction]在一位调查员抽出[auto_fail]混乱标记时：取消该标记并将它视为
[elder_sign]标记。(每场游戏限制一次。)
远古印记：你自动成功。在本次检定结束后，选择以下一项：
 - 抽取1张卡牌并获得1资源。
 - 如果此时是你的回合，本回合你可以进行额外一个行动。

简化说明：
- 取消自动失败经引擎既有通道 ctx.extra["cancel_auto_fail"]（skill_test 的
  ST.4 据此清除 auto_fail）；"视为远古印记"通过把 ctx.chaos_token 改写为
  ELDER_SIGN + 设置 ctx.extra["father_mateo_converted"] 实现：注册顺序晚于
  马泰奥的 WHEN 处理器会看到 ELDER_SIGN，注册更早的处理器可检查
  father_mateo_converted 标记（本批次调查员的印记处理器均已检查该标记；
  更早注册的其他调查员印记效果可能miss——引擎缺口：无标记改写通道）。
  马泰奥须在游戏中（未要求存活检查，与既有调查员实现一致）。
- "你自动成功"：在 SKILL_TEST_FAILED 时把 ctx.success 置 True（引擎 ST.6
  据此翻转结果），比 +999 近似更精确。
- 检定结束后的二选一：同步流程无法等待玩家选择，经
  scenario.vars["father_mateo_elder_choice"] 预设（"draw" / "action"），
  缺省 "draw"；预设 "action" 但不是他的回合时回退为 "draw"（官方此时
  不可选第二项）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import ChaosTokenType, GameEvent, TimingPriority


class FatherMateo(CardImplementation):
    card_id = "father_mateo"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._used_this_game = False
        self._auto_success = False
        self._my_turn = False

    def _get_mateo(self, game_state, investigator_id):
        """Return the investigator state iff it is Father Mateo."""
        if investigator_id is None:
            return None
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return None
        card_data = getattr(inv, "card_data", None)
        if card_data is None or card_data.id != "father_mateo":
            return None
        return inv

    def _mateo_in_game(self, game_state):
        """返回游戏中的马泰奥（任意玩家位）。"""
        for inv in game_state.investigators.values():
            card_data = getattr(inv, "card_data", None)
            if card_data is not None and card_data.id == "father_mateo":
                return inv
        return None

    @on_event(GameEvent.INVESTIGATOR_TURN_BEGINS, priority=TimingPriority.AFTER)
    def track_turn_begin(self, ctx):
        if self._get_mateo(ctx.game_state, ctx.investigator_id) is not None:
            self._my_turn = True

    @on_event(GameEvent.INVESTIGATOR_TURN_ENDS, priority=TimingPriority.AFTER)
    def track_turn_end(self, ctx):
        if self._get_mateo(ctx.game_state, ctx.investigator_id) is not None:
            self._my_turn = False

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.WHEN)
    def cancel_auto_fail(self, ctx):
        """[reaction] 一位调查员抽出自动失败时：取消并视为远古印记（每场限1次）。"""
        if ctx.chaos_token == ChaosTokenType.AUTO_FAIL \
                and not self._used_this_game \
                and self._mateo_in_game(ctx.game_state) is not None:
            self._used_this_game = True
            ctx.extra["cancel_auto_fail"] = True
            ctx.extra["father_mateo_converted"] = True
            ctx.chaos_token = ChaosTokenType.ELDER_SIGN
            ctx.game_state.log_effect(
                "✝️ 马泰奥神父：取消自动失败，视为远古印记"
            )

        # 马泰奥本人的远古印记：自动成功
        if ctx.chaos_token != ChaosTokenType.ELDER_SIGN \
                and not ctx.extra.get("father_mateo_converted"):
            return
        if self._get_mateo(ctx.game_state, ctx.investigator_id) is None:
            return
        self._auto_success = True
        ctx.game_state.log_effect("✝️ 马泰奥神父：远古印记，自动成功")

    @on_event(GameEvent.SKILL_TEST_FAILED, priority=TimingPriority.WHEN)
    def apply_auto_success(self, ctx):
        """远古印记：检定失败时翻转为成功。"""
        if not self._auto_success:
            return
        if self._get_mateo(ctx.game_state, ctx.investigator_id) is None:
            return
        ctx.success = True
        ctx.extra["father_mateo_auto_success"] = True

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def post_test_choice(self, ctx):
        """远古印记检定结束后：抽1牌+1资源，或（他的回合）+1行动。"""
        if not self._auto_success:
            return
        inv = self._get_mateo(ctx.game_state, ctx.investigator_id)
        self._auto_success = False
        if inv is None:
            return

        scenario = getattr(ctx.game_state, "scenario", None)
        choice = scenario.vars.get("father_mateo_elder_choice", "draw") \
            if scenario is not None else "draw"
        if choice == "action" and self._my_turn:
            inv.actions_remaining += 1
            ctx.game_state.log_effect("✝️ 马泰奥神父：本回合获得额外1个行动")
        else:
            if inv.deck:
                inv.hand.append(inv.deck.pop(0))
            inv.resources += 1
            ctx.game_state.log_effect("✝️ 马泰奥神父：抽1张牌并获得1资源")
