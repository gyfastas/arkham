"""Rite of Sanctification (Level 0) — Guardian Asset, Arcane slot. (07019)
封印(最多5[bless])。如果成圣仪式上没有封印的标记，将其丢弃。
[reaction]你所在地点一位调查员在打出一张卡牌时，消耗成圣仪式并释放其上
封印的一个混乱标记：该卡牌费用降低2。

简化说明：
- 入场时自动从混乱袋封印至多5个祝福标记（官方为"最多"，自动取最大值）。
- 减费时机在引擎费用结算之前没有可拦截窗口（_play 先扣费再发
  CARD_PLAYED），实现为打出后返还2资源（净效果等价于费用-2，但玩家须
  先付得起原价，列为引擎缺口）。引擎仅对事件卡发出 CARD_PLAYED，
  对支援卡打出不触发本反应（同为引擎缺口，注明）。
- 释放最后一个封印标记后本卡丢弃（镜像引擎离场流程）。
"""

from backend.cards._shared import defeat_asset
from backend.cards.base import CardImplementation, on_event
from backend.models.enums import ChaosTokenType, GameEvent, TimingPriority

_MAX_SEAL = 5
_COST_REDUCTION = 2


class RiteOfSanctification(CardImplementation):
    card_id = "rite_of_sanctification_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._bag = None
        self._bus = None
        self._sealed = 0

    def bind_chaos_bag(self, bag) -> None:
        self._bag = bag

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus

    @on_event(GameEvent.CARD_ENTERS_PLAY, priority=TimingPriority.AFTER)
    def seal_on_enter(self, ctx):
        """入场：从混乱袋封印至多5个祝福标记；一个没有则丢弃。"""
        if ctx.target != self.instance_id:
            return
        if self._bag is not None:
            while self._sealed < _MAX_SEAL and self._bag.seal_token(ChaosTokenType.BLESS):
                self._sealed += 1
        if self._sealed:
            ctx.game_state.log_effect(
                f"📿 成圣仪式：封印{self._sealed}个祝福标记")
        else:
            defeat_asset(ctx.game_state, self._bus, self.instance_id)
            ctx.game_state.log_effect("📿 成圣仪式：没有封印的标记，丢弃")

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.AFTER)
    def reduce_cost(self, ctx):
        """同地点调查员打出卡牌时：消耗并释放1个封印标记，返还2资源。"""
        if ctx.extra.get("card_id") == self.card_id:
            return
        holder = self._holder(ctx.game_state)
        if holder is None:
            return
        player = ctx.game_state.get_investigator(ctx.investigator_id)
        if player is None or player.location_id != holder.location_id:
            return
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None or inst.exhausted or self._sealed <= 0:
            return

        inst.exhausted = True
        self._sealed -= 1
        if self._bag is not None:
            self._bag.release_token(ChaosTokenType.BLESS)
        player.resources += _COST_REDUCTION  # 返还（净效果=费用-2，见 docstring）
        ctx.game_state.log_effect(
            f"📿 成圣仪式：消耗并释放1个封印标记，"
            f"【{ctx.game_state.card_name(ctx.extra.get('card_id'))}】费用降低2")

        if self._sealed <= 0:
            defeat_asset(ctx.game_state, self._bus, self.instance_id)
            ctx.game_state.log_effect("📿 成圣仪式：没有封印的标记，丢弃")

    def _holder(self, game_state):
        for inv in game_state.investigators.values():
            if self.instance_id in inv.play_area:
                return inv
        return None
