"""Protective Gear (Level 2) — Guardian Asset, Body slot. (08095)
生命3/理智3。
[reaction]在你抽取一张[[危险]]诡计卡时，对防护服造成1点伤害和1点恐惧：
取消该卡牌的显现效果。

简化说明：
- 自动触发（官方为玩家选择时机）：持有者抽到 Hazard 诡计（遭遇牌堆，
  ENCOUNTER_CARD_DRAWN）时自动承伤承恐并标记取消。
- 取消经 scenario.vars["cancelled_encounter"] 标记提供给会话层跳过结算
  （与 ward_of_protection 同一约定）。
- 承伤承恐达到生命/理智上限时防护服被击败离场（镜像引擎离场流程）。
"""

from backend.cards._shared import defeat_asset
from backend.cards.base import CardImplementation, on_event
from backend.models.enums import CardType, GameEvent, TimingPriority


class ProtectiveGear(CardImplementation):
    card_id = "protective_gear_lv2"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._bus = None

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus

    @on_event(GameEvent.ENCOUNTER_CARD_DRAWN, priority=TimingPriority.WHEN)
    def cancel_hazard(self, ctx):
        """持有者抽到危险诡计：对防护服造成1伤害1恐惧，取消显现。"""
        card_id = ctx.extra.get("card_id")
        cd = ctx.game_state.get_card_data(card_id) if card_id else None
        if cd is None or cd.type != CardType.TREACHERY:
            return
        if "hazard" not in (cd.traits or []):
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        inst = ctx.game_state.get_card_instance(self.instance_id)
        data = ctx.game_state.get_card_data(inst.card_id) if inst else None
        if inst is None or data is None:
            return

        # 对防护服造成1伤害1恐惧
        inst.damage += 1
        inst.horror += 1

        # 取消显现（会话层消费）
        ctx.game_state.scenario.vars["cancelled_encounter"] = card_id
        ctx.extra["protective_gear_cancelled"] = card_id
        ctx.game_state.log_effect(
            f"🥽 防护服：承受1伤害1恐惧，取消【{ctx.game_state.card_name(card_id)}】的显现")

        # 耐久耗尽则被击败
        defeated = (
            (data.health is not None and inst.damage >= data.health)
            or (data.sanity is not None and inst.horror >= data.sanity)
        )
        if defeated:
            defeat_asset(ctx.game_state, self._bus, self.instance_id)
            ctx.game_state.log_effect("🥽 防护服：耐久耗尽，被击败")
