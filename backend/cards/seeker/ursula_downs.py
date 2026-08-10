"""Ursula Downs — Seeker Investigator.
能力：[reaction]在你移动到一个地点后：进行一次调查行动。(每轮限制1次。)
远古印记：+1。在本次检定结束后，你可以移动到一个连接地点。

简化说明：
- "移动后进行一次调查行动"：ACTION_PERFORMED（移动）时置位（引擎的
  MOVE_ACTION_INITIATED 在换位前发出，无法直接调查新地点），免费调查经公开
  方法 activate_free_investigate() 执行（由 UI/会话层在玩家确认后调用；
  同步事件流无法等待玩家输入）。该调查是反应能力赋予的行动，不扣行动数；
  不引发趁乱攻击（不经过 perform_action，简化）。
- 免费调查复刻 ActionResolver._investigate：发出 INVESTIGATE_ACTION_INITIATED
  后跑智力检定，成功则发现线索并发出 CLUE_DISCOVERED。
- 远古印记的"检定结束后移动"：标记保留至下一次检定开始（SKILL_TEST_BEGINS
  清除），经公开方法 activate_elder_move() 执行（目标须为连接地点）。
- 马泰奥神父将自动失败转为远古印记时（father_mateo_converted 标记），本卡
  同样按远古印记结算。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import (
    Action, ChaosTokenType, GameEvent, Skill, TimingPriority,
)


class UrsulaDowns(CardImplementation):
    card_id = "ursula_downs"

    activations = [
        {
            "id": "free_investigate",
            "label": "【响应】移动后：进行一次调查行动",
            "method": "activate_free_investigate",
        },
        {
            "id": "elder_move",
            "label": "远古印记：检定结束后移动到一个连接地点",
            "method": "activate_elder_move",
        },
    ]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._investigate_armed = False
        self._used_this_round = False
        self._elder_move_pending = False

    def _get_ursula(self, game_state, investigator_id):
        """Return the investigator state iff it is Ursula Downs."""
        if investigator_id is None:
            return None
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return None
        card_data = getattr(inv, "card_data", None)
        if card_data is None or card_data.id != "ursula_downs":
            return None
        return inv

    @on_event(GameEvent.ROUND_BEGINS, priority=TimingPriority.WHEN)
    def reset_round_limit(self, ctx):
        """每轮开始时重置限次。"""
        self._used_this_round = False
        self._investigate_armed = False

    @on_event(GameEvent.ACTION_PERFORMED, priority=TimingPriority.AFTER)
    def arm_investigate_on_move(self, ctx):
        """在你移动到一个地点后：武装一次免费调查（每轮限1次）。"""
        if self._used_this_round or ctx.action != Action.MOVE:
            return
        inv = self._get_ursula(ctx.game_state, ctx.investigator_id)
        if inv is None:
            return
        self._used_this_round = True
        self._investigate_armed = True
        ctx.extra["ursula_downs_investigate_armed"] = True
        ctx.game_state.log_effect("🧭 厄休拉·唐斯：移动后可进行一次调查行动")

    def activate_free_investigate(self, game, investigator_id,
                                  committed_cards=None) -> bool:
        """[reaction] 移动后：进行一次调查行动（不扣行动数）。由 UI 调用。"""
        game_state = game.state
        inv = self._get_ursula(game_state, investigator_id)
        if inv is None or not self._investigate_armed:
            return False
        location = game_state.get_location(inv.location_id)
        if location is None:
            return False
        self._investigate_armed = False

        from backend.engine.event_bus import EventContext
        game.event_bus.emit(EventContext(
            game_state=game_state,
            event=GameEvent.INVESTIGATE_ACTION_INITIATED,
            investigator_id=investigator_id,
            location_id=inv.location_id,
        ))

        def on_success(result):
            if location.clues > 0:
                location.clues -= 1
                inv.clues += 1
                game.event_bus.emit(EventContext(
                    game_state=game_state,
                    event=GameEvent.CLUE_DISCOVERED,
                    investigator_id=investigator_id,
                    location_id=inv.location_id,
                    amount=1,
                ))

        game.skill_test_engine.run_test(
            investigator_id=investigator_id,
            skill_type=Skill.INTELLECT,
            difficulty=location.shroud,
            committed_card_ids=committed_cards or [],
            on_success=on_success,
        )
        return True

    @on_event(GameEvent.SKILL_TEST_BEGINS, priority=TimingPriority.WHEN)
    def close_elder_move_window(self, ctx):
        """新检定开始时关闭上一次的印记移动窗口。"""
        self._elder_move_pending = False

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.WHEN)
    def elder_sign_effect(self, ctx):
        """远古印记：+1。本次检定结束后可移动到一个连接地点。"""
        if ctx.chaos_token != ChaosTokenType.ELDER_SIGN \
                and not ctx.extra.get("father_mateo_converted"):
            return
        inv = self._get_ursula(ctx.game_state, ctx.investigator_id)
        if inv is None:
            return
        ctx.modify_amount(1, "ursula_downs_elder_sign")
        self._elder_move_pending = True

    def activate_elder_move(self, game_state, investigator_id,
                            destination) -> bool:
        """远古印记：检定结束后移动到一个连接地点。由 UI 调用。"""
        inv = self._get_ursula(game_state, investigator_id)
        if inv is None or not self._elder_move_pending:
            return False
        current_loc = game_state.get_location(inv.location_id)
        if current_loc is None or destination not in current_loc.connections:
            return False
        self._elder_move_pending = False
        inv.location_id = destination
        game_state.log_effect(
            f"🧭 厄休拉·唐斯：远古印记，移动到【{destination}】"
        )
        return True
