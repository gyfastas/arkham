"""Guiding Spirit (Level 1) — Survivor Asset, Ally slot. (05236)
You get +1 [intellect].
Non-direct horror must be assigned to Guiding Spirit before it can be
assigned to your investigator card.
Forced - When Guiding Spirit is defeated by horror: Exile it.

简化说明：
- "必须优先分配"实现为 HORROR_ASSIGNED 拦截（同 plucky_lv1）：非直接恐惧
  落到调查员前自动先由引路精灵承担（不超过其剩余理智）；引擎只在非直接
  路径发此事件，天然排除直接恐惧。
- 被恐惧击败时放逐：引擎无放逐区，登记 scenario.vars["exiled_cards"]
  （同 devils_luck 模式）；引擎通道击败（ASSET_DEFEATED 后入弃牌堆）的
  情况由 AFTER 处理改写为放逐。
"""

from backend.cards.base import CardImplementation, on_event
from backend.engine.slots import vacate_asset_slots
from backend.models.enums import GameEvent, Skill, TimingPriority


class GuidingSpirit(CardImplementation):
    card_id = "guiding_spirit_lv1"

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def intellect_bonus(self, ctx):
        """+1 Intellect while Guiding Spirit is in play."""
        if ctx.skill_type != Skill.INTELLECT:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv and self.instance_id in inv.play_area:
            ctx.modify_amount(1, "guiding_spirit_intellect")

    @on_event(GameEvent.HORROR_ASSIGNED, priority=TimingPriority.WHEN)
    def soak_horror_first(self, ctx):
        """非直接恐惧必须先分给引路精灵（自动承恐至剩余理智上限）。"""
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None:
            return
        cd = ctx.game_state.get_card_data(self.card_id)
        capacity = ((cd.sanity or 0) - inst.horror) if cd else 0
        take = min(capacity, ctx.amount or 0)
        if take <= 0:
            return
        inst.horror += take
        ctx.modify_amount(-take, "guiding_spirit_soak")
        ctx.game_state.log_effect(f"👻 引路精灵：优先承受{take}点恐惧")

        # 恐惧达到理智上限被击败：放逐而非弃置（内联结算，同 plucky 模式）
        if cd is not None and cd.sanity is not None and inst.horror >= cd.sanity:
            self._exile(ctx, inv)

    @on_event(GameEvent.ASSET_DEFEATED, priority=TimingPriority.AFTER)
    def exile_on_defeat(self, ctx):
        """引擎通道被击败（已入弃牌堆）时改写为放逐。"""
        if ctx.target != self.instance_id:
            return
        for other in ctx.game_state.investigators.values():
            if self.card_id in other.discard:
                other.discard.remove(self.card_id)
                ctx.game_state.scenario.vars.setdefault(
                    "exiled_cards", []).append(self.card_id)
                ctx.game_state.log_effect("👻 引路精灵被恐惧击败，放逐")
                return

    def _exile(self, ctx, inv) -> None:
        vacate_asset_slots(ctx.game_state, self.instance_id)
        if self.instance_id in inv.play_area:
            inv.play_area.remove(self.instance_id)
        ctx.game_state.cards_in_play.pop(self.instance_id, None)
        ctx.game_state.scenario.vars.setdefault(
            "exiled_cards", []).append(self.card_id)
        ctx.game_state.log_effect("👻 引路精灵恐惧达到上限被击败，放逐")
