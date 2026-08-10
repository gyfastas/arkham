"""Sign Magick (Level 0) — Mystic Asset, Hand slot, fast. (05112)
快速。你拥有1个额外的奥秘槽位，该槽位只能放置[[法术]]或[[仪式]]支援卡。

简化说明：
- 额外奥秘槽经 SlotManager 的限制性奖励槽实现（同 daisys_tote_bag 模式）。
  该实现每个 source 只支持单条特质记录，故法术/仪式以 "{instance_id}:spell"
  / "{instance_id}:ritual" 两个 source 各登记一条（极端情况下可同时被一张
  法术和一张仪式各占1个——与官方"共1槽"略有偏差，引擎缺口）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, SlotType, TimingPriority


class SignMagick(CardImplementation):
    card_id = "sign_magick_lv0"
    bonus_traits = ("spell", "ritual")

    @on_event(GameEvent.CARD_ENTERS_PLAY, priority=TimingPriority.AFTER)
    def enter_play(self, ctx):
        """进场：+1个仅限法术/仪式的奥秘槽位。"""
        if ctx.target != self.instance_id:
            return
        mgr = getattr(ctx.game_state, "slot_managers", {}).get(ctx.investigator_id)
        if mgr is None:
            return
        for trait in self.bonus_traits:
            mgr.add_restricted_bonus(
                SlotType.ARCANE, 1, trait=trait,
                source=f"{self.instance_id}:{trait}")

    @on_event(GameEvent.CARD_LEAVES_PLAY, priority=TimingPriority.AFTER)
    def leaves_play(self, ctx):
        if ctx.target != self.instance_id:
            return
        mgr = getattr(ctx.game_state, "slot_managers", {}).get(ctx.investigator_id)
        if mgr is not None:
            for trait in self.bonus_traits:
                mgr.remove_restricted_bonus(
                    SlotType.ARCANE, source=f"{self.instance_id}:{trait}")
