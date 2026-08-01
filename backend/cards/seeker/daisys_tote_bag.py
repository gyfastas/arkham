"""Daisy's Tote Bag — Seeker Asset (Signature).
提供2个额外手部栏位，只能用于放置典籍(Tome)支援卡。

实现说明：
- 通过 SlotManager 的 restricted bonus 授予：只有带 tome trait 的卡
  才能使用这 2 个额外手槽（官方规则）。
- uses["tome_hand_slots"] 作为标记保留，供 UI 提示使用。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, SlotType, TimingPriority


class DaisysToteBag(CardImplementation):
    card_id = "daisys_tote_bag"
    slot_type = SlotType.HAND
    bonus = 2

    @on_event(
        GameEvent.CARD_ENTERS_PLAY,
        priority=TimingPriority.AFTER,
    )
    def grant_tome_slots(self, ctx):
        """When Tote Bag enters play, grant 2 extra hand slots."""
        if ctx.target != self.instance_id:
            return
        mgr = getattr(ctx.game_state, "slot_managers", {}).get(ctx.investigator_id)
        if mgr is not None:
            mgr.add_restricted_bonus(
                self.slot_type, self.bonus, trait="tome", source=self.instance_id
            )
        # 标记在卡上，供 UI 显示“仅典籍”提示
        ci = ctx.game_state.get_card_instance(self.instance_id)
        if ci:
            ci.uses = ci.uses or {}
            ci.uses["tome_hand_slots"] = self.bonus

    @on_event(
        GameEvent.CARD_LEAVES_PLAY,
        priority=TimingPriority.AFTER,
    )
    def remove_tome_slots(self, ctx):
        """When Tote Bag leaves play, remove the extra slots."""
        if ctx.target != self.instance_id:
            return
        mgr = getattr(ctx.game_state, "slot_managers", {}).get(ctx.investigator_id)
        if mgr is not None:
            mgr.remove_restricted_bonus(self.slot_type, source=self.instance_id)
        ci = ctx.game_state.get_card_instance(self.instance_id)
        if ci and ci.uses:
            ci.uses.pop("tome_hand_slots", None)
