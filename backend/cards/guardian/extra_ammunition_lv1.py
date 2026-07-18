"""Extra Ammunition (Level 1) — Guardian Event.
在你打出一张有"使用(弹药)"的支援卡后：在其上放置2弹药。

简化说明：
- 打出时：选择你控制的一张含弹药(ammo)的支援卡，在其上放置2弹药。
  默认选第一张有弹药的支援，可用 ctx.extra["target_instance"] 指定。
- 中文卡面首行（手槽位上限）为翻译串行，未实现。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class ExtraAmmunition(CardImplementation):
    card_id = "extra_ammunition_lv1"

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def add_ammo(self, ctx):
        if ctx.extra.get("card_id") != "extra_ammunition_lv1":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return

        target = None
        target_iid = ctx.extra.get("target_instance")
        if target_iid:
            target = ctx.game_state.get_card_instance(target_iid)
        else:
            for iid in inv.play_area:
                inst = ctx.game_state.get_card_instance(iid)
                if inst is not None and inst.uses.get("ammo") is not None:
                    target = inst
                    break
        if target is None:
            return
        target.uses["ammo"] = target.uses.get("ammo", 0) + 2
        ctx.extra["extra_ammunition_target"] = target.instance_id
