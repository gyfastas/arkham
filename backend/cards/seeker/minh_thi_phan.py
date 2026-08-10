"""Minh Thi Phan — Seeker Investigator.
能力：[reaction]你所在地点的调查员在技能检定中投入一张卡牌后：在此次技能检定结束前，
该卡牌获得1个[wild]图标。(每位调查员每轮限制1次。)
远古印记：+1。本次技能检定结束后，你可以选择投入本次技能检定的一张技能卡返回其
所有者的手牌。

简化说明：
- 引擎的投入图标合计（engine/skill_test.py ST.2）把 wild 图标计入任意技能检定，
  因此"该卡获得1个[wild]图标"数值上等价于本次检定总投入图标+1；实现为
  SKILL_TEST_COMMIT 时 ctx.amount+1，并在 ctx.extra["minh_wild_icon_card"] 记录
  获得图标的卡（自动选第一张投入卡，官方为触发玩家选择——数值等价）。
- 远古印记的回手：官方为检定结束后玩家选择一张投入的技能卡。实现为自动选择本次
  检定投入的第一张技能卡（SKILL_TEST_ENDS 时投入的卡已被引擎移入所有者弃牌堆，
  从弃牌堆取回）；可在触发前设置 scenario.vars["minh_thi_phan_return"] = card_id
  指定要回手的技能卡（须为本检定投入的技能卡之一），与 agnes_baker_target 同一惯例。
- 引擎投入通道只支持检定者本人投入手牌（ST.8 只从检定者手牌弃置投入卡），
  跨调查员投入由他卡表达（如 analytical_mind），与本能力正交。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import (
    CardType, ChaosTokenType, GameEvent, TimingPriority,
)


class MinhThiPhan(CardImplementation):
    card_id = "minh_thi_phan"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        # 每位调查员每轮限1次：本轮已受益的调查员 id 集合
        self._used_this_round: set[str] = set()
        # 本检定投入的卡（SKILL_TEST_COMMIT 快照，供远古印记回手）
        self._committed: list[str] = []
        self._elder_sign_armed = False

    def _find_minh(self, game_state):
        """Return the investigator state of Minh Thi Phan, if in play."""
        for inv in game_state.investigators.values():
            card_data = getattr(inv, "card_data", None)
            if card_data is not None and card_data.id == "minh_thi_phan":
                return inv
        return None

    @on_event(GameEvent.ROUND_BEGINS, priority=TimingPriority.WHEN)
    def reset_round_limit(self, ctx):
        """每轮开始时重置每位调查员的限次。"""
        self._used_this_round.clear()

    @on_event(GameEvent.SKILL_TEST_COMMIT, priority=TimingPriority.REACTION)
    def grant_wild_icon(self, ctx):
        """你所在地点的调查员投入一张卡牌后：该卡获得1个[wild]图标（每调查员每轮限1次）。"""
        if not ctx.committed_cards:
            return
        committer = ctx.game_state.get_investigator(ctx.investigator_id)
        if committer is None or committer.investigator_id in self._used_this_round:
            return
        minh = self._find_minh(ctx.game_state)
        if minh is None or minh.location_id != committer.location_id:
            return

        self._used_this_round.add(committer.investigator_id)
        # 本实现挂靠在潘明的调查员实例上；多潘明实例（不应出现）会重复注册，
        # 以 used 集合幂等。
        ctx.modify_amount(1, "minh_thi_phan_wild_icon")
        ctx.extra["minh_wild_icon_card"] = ctx.committed_cards[0]
        ctx.game_state.log_effect(
            f"📋 潘明：【{ctx.game_state.card_name(ctx.committed_cards[0])}】"
            "获得1个[wild]图标"
        )

    @on_event(GameEvent.SKILL_TEST_COMMIT, priority=TimingPriority.AFTER)
    def track_committed(self, ctx):
        """快照本检定投入的卡，供远古印记回手。"""
        self._committed = list(ctx.committed_cards or [])

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.WHEN)
    def elder_sign_effect(self, ctx):
        """远古印记：+1。武装"检定结束后技能卡回手"。"""
        if ctx.chaos_token != ChaosTokenType.ELDER_SIGN:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        card_data = getattr(inv, "card_data", None) if inv else None
        if card_data is None or card_data.id != "minh_thi_phan":
            return
        ctx.modify_amount(1, "minh_thi_phan_elder_sign")
        self._elder_sign_armed = True

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def return_committed_skill(self, ctx):
        """检定结束后：选择一张投入的技能卡返回其所有者手牌（简化：自动选第一张）。"""
        armed = self._elder_sign_armed
        committed, self._committed = self._committed, []
        self._elder_sign_armed = False
        if not armed:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        card_data = getattr(inv, "card_data", None) if inv else None
        if card_data is None or card_data.id != "minh_thi_phan":
            return

        skill_cards = [
            cid for cid in committed
            if (cd := ctx.game_state.get_card_data(cid)) is not None
            and cd.type == CardType.SKILL
        ]
        if not skill_cards:
            return

        scenario = getattr(ctx.game_state, "scenario", None)
        override = None
        if scenario is not None:
            override = scenario.vars.pop("minh_thi_phan_return", None)
        chosen = override if override in skill_cards else skill_cards[0]

        # 投入的卡已被引擎移入所有者弃牌堆（ST.8）；从弃牌堆取回
        if chosen in inv.discard:
            inv.discard.remove(chosen)
            inv.hand.append(chosen)
            ctx.game_state.log_effect(
                f"📋 潘明：【{ctx.game_state.card_name(chosen)}】返回所有者手牌"
            )
