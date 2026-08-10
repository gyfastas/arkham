"""Treasure Hunter (Level 1) — Rogue Asset, Ally. (04025)
你获得+1[intellect]。
强制 - 当补给阶段结束时：你必须支付1资源或丢弃寻宝猎人。

简化说明：
- 强制二选一自动决策：资源足够则支付1资源，否则丢弃（支付保留盟友是
  占优选择；官方为玩家选择）。
- 丢弃复刻引擎资产离场流程（ASSET_DEFEATED/CARD_LEAVES_PLAY + 槽位释放）。
"""

from backend.cards._shared import defeat_asset
from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class TreasureHunter(CardImplementation):
    card_id = "treasure_hunter_lv1"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._bus = None

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus  # 被丢弃时需要经事件总线发出离场事件

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def intellect_bonus(self, ctx):
        """+1智力（在场时持续生效）。"""
        if ctx.skill_type != Skill.INTELLECT:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        ctx.modify_amount(1, "treasure_hunter_intellect")

    @on_event(GameEvent.UPKEEP_PHASE_ENDS, priority=TimingPriority.FORCED)
    def pay_or_discard(self, ctx):
        """强制 - 补给阶段结束时：支付1资源，否则丢弃。"""
        owner = None
        for inv in ctx.game_state.investigators.values():
            if self.instance_id in inv.play_area:
                owner = inv
                break
        if owner is None:
            return
        if owner.resources >= 1:
            owner.resources -= 1
            ctx.extra["treasure_hunter_paid"] = True
            ctx.game_state.log_effect("🧭 寻宝猎人：补给阶段结束，支付1资源保留")
        else:
            ctx.extra["treasure_hunter_discarded"] = True
            ctx.game_state.log_effect("🧭 寻宝猎人：无法支付1资源，被丢弃")
            defeat_asset(ctx.game_state, self._bus, self.instance_id)
