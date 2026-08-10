"""Unscrupulous Loan (Level 3) — Rogue Asset. (08113)
每位调查员限制1张。不能离场。
[reaction] 在你打出大肆借贷后：获得10资源。
强制 - 在游戏结束或你退场时，如果你的资源池中的资源少于10：放逐大肆借贷。

简化说明：
- "打出后获得10资源"挂 CARD_ENTERS_PLAY。
- "你退场"经 INVESTIGATOR_DEFEATED 捕获：资源<10则放逐（记入
  scenario.vars["removed_from_game"]，同一惯例）。
- "游戏结束"无事件（引擎缺口），游戏结束时的放逐校验未实现。
- "不能离场"：引擎的离场流程无取消通道（引擎缺口），仅数据层语义。
- "每位调查员限制1张"为入场规则，引擎无校验通道（引擎缺口）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority

_LOAN_AMOUNT = 10


class UnscrupulousLoan(CardImplementation):
    card_id = "unscrupulous_loan_lv3"

    @on_event(GameEvent.CARD_ENTERS_PLAY, priority=TimingPriority.REACTION)
    def gain_loan(self, ctx):
        """打出后：获得10资源。"""
        if ctx.target != self.instance_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        inv.resources += _LOAN_AMOUNT
        ctx.extra["unscrupulous_loan_gained"] = _LOAN_AMOUNT
        ctx.game_state.log_effect(f"💸 大肆借贷：获得{_LOAN_AMOUNT}资源")

    @on_event(GameEvent.INVESTIGATOR_DEFEATED, priority=TimingPriority.FORCED)
    def exile_on_elimination(self, ctx):
        """强制 - 你退场时资源不足10：放逐大肆借贷。"""
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        if inv.resources >= _LOAN_AMOUNT:
            return
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None:
            return
        inv.play_area.remove(self.instance_id)
        ctx.game_state.cards_in_play.pop(self.instance_id, None)
        ctx.game_state.scenario.vars.setdefault(
            "removed_from_game", []).append(self.card_id)
        ctx.extra["unscrupulous_loan_exiled"] = True
        ctx.game_state.log_effect("💸 大肆借贷：退场时资源不足10，被放逐")
