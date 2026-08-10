"""Rod of Animalism (Level 1) — Neutral Asset. (08128)
你获得2个额外的盟友槽位，只能用于放置[[生物]]支援卡。
[reaction]当你在你的回合打出一张[[生物]]支援卡时：该支援卡费用降低1。

简化说明：
- 额外盟友槽经 SlotManager.add_restricted_bonus（"creature" 限定）实现，
  参照 charisma_lv3 的 CARD_ENTERS_PLAY/CARD_LEAVES_PLAY 挂接。
- 费用降低实现为打出后返还1资源（引擎在 CARD_ENTERS_PLAY 前已全额扣费，
  无打出前改费通道）；仅当所付费用≥1时返还。
- "在你的回合"无法从事件判定（回合归属由会话层维护），简化为任何时刻打出
  均触发返还。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import CardType, GameEvent, SlotType, TimingPriority


class RodOfAnimalism(CardImplementation):
    card_id = "rod_of_animalism_lv1"

    @on_event(GameEvent.CARD_ENTERS_PLAY, priority=TimingPriority.AFTER)
    def enter_play(self, ctx):
        if ctx.target != self.instance_id:
            return
        mgr = getattr(ctx.game_state, "slot_managers", {}).get(ctx.investigator_id)
        if mgr is not None:
            mgr.add_restricted_bonus(SlotType.ALLY, 2, "creature", self.instance_id)

    @on_event(GameEvent.CARD_LEAVES_PLAY, priority=TimingPriority.AFTER)
    def leaves_play(self, ctx):
        if ctx.target != self.instance_id:
            return
        mgr = getattr(ctx.game_state, "slot_managers", {}).get(ctx.investigator_id)
        if mgr is not None:
            mgr.remove_restricted_bonus(SlotType.ALLY, self.instance_id)

    @on_event(GameEvent.CARD_ENTERS_PLAY, priority=TimingPriority.AFTER)
    def refund_creature_cost(self, ctx):
        """打出生物支援卡：返还1资源（费用降低的等价实现）。"""
        if ctx.target == self.instance_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        card_id = ctx.extra.get("card_id")
        cd = ctx.game_state.get_card_data(card_id) if card_id else None
        if cd is None or cd.type != CardType.ASSET:
            return
        if "creature" not in (cd.traits or []):
            return
        if (cd.cost or 0) >= 1:
            inv.resources += 1
            ctx.extra["rod_of_animalism_refund"] = 1
