"""Extra Ammunition (Level 1) — Guardian Event.
在你所在地点的一位调查员控制的[枪械]支援上放置3弹药。

简化说明：
- 打出时默认选你装备区第一把枪械；可用 ctx.extra["target_instance"]
  指定目标（必须是同地点调查员控制的枪械，否则不生效）。
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
            # 指定目标：必须是同地点调查员控制的枪械
            if self._is_firearm_at_location(ctx, target_iid, inv.location_id):
                target = ctx.game_state.get_card_instance(target_iid)
        else:
            # 默认：同地点调查员（自己优先）装备区的第一把枪械
            investigators = [inv] + [
                other for other in ctx.game_state.get_investigators_at_location(
                    inv.location_id)
                if other.investigator_id != inv.investigator_id
            ]
            for other in investigators:
                for iid in other.play_area:
                    if self._is_firearm_at_location(ctx, iid, inv.location_id):
                        target = ctx.game_state.get_card_instance(iid)
                        break
                if target is not None:
                    break
        if target is None:
            return
        target.uses["ammo"] = target.uses.get("ammo", 0) + 3
        ctx.extra["extra_ammunition_target"] = target.instance_id

    @staticmethod
    def _is_firearm_at_location(ctx, instance_id: str, location_id: str) -> bool:
        inst = ctx.game_state.get_card_instance(instance_id)
        if inst is None:
            return False
        data = ctx.game_state.get_card_data(inst.card_id)
        traits = {t.lower() for t in (getattr(data, "traits", []) or [])} if data else set()
        if "firearm" not in traits:
            return False
        controller = ctx.game_state.get_investigator(inst.controller_id)
        return (controller is not None
                and controller.location_id == location_id
                and instance_id in controller.play_area)
