"""First Aid (Level 0) — Guardian Asset.
使用(3补给)。如果急救没有补给，弃置它。
[行动]花费1补给：治愈你所在地点一名调查员的1点伤害或1点恐惧。

简化说明：
- 通用激活通道只传 (game_state, investigator_id)，默认治愈自己；
  会话层可传 target_investigator_id 指定同地点的其他调查员。
- 未指定 heal 时自动选择：优先治愈伤害，无伤害则治愈恐惧。
"""

from backend.cards.base import CardImplementation
from backend.engine.slots import vacate_asset_slots


class FirstAid(CardImplementation):
    card_id = "first_aid_lv0"
    activations = [{"id": "heal", "label": "花1补给：治愈1伤害或1恐惧", "method": "activate"}]
    supplies_key = "supplies"

    def activate(self, game_state, investigator_id: str,
                 target_investigator_id: str | None = None,
                 heal: str | None = None) -> bool:
        """花费1补给：治愈目标1点伤害或1点恐惧（默认治愈自己）。"""
        inv = game_state.get_investigator(investigator_id)
        inst = game_state.get_card_instance(self.instance_id)
        if inv is None or inst is None:
            return False
        if self.instance_id not in inv.play_area:
            return False
        if inst.uses.get(self.supplies_key, 0) <= 0:
            return False

        target = game_state.get_investigator(target_investigator_id or investigator_id)
        if target is None or target.location_id != inv.location_id:
            return False

        if not self._heal(target, heal):
            return False

        inst.uses[self.supplies_key] -= 1
        if inst.uses[self.supplies_key] <= 0:
            self._discard_self(game_state, inv)
        return True

    def _heal(self, target, heal: str | None) -> bool:
        """治愈1点伤害或恐惧；heal 可为 "damage"/"horror"/None(自动)。"""
        if heal == "damage":
            if target.damage <= 0:
                return False
            target.damage -= 1
            return True
        if heal == "horror":
            if target.horror <= 0:
                return False
            target.horror -= 1
            return True
        # 自动：优先伤害，其次恐惧
        if target.damage > 0:
            target.damage -= 1
            return True
        if target.horror > 0:
            target.horror -= 1
            return True
        return False

    def _discard_self(self, game_state, inv) -> None:
        """补给耗尽：弃置急救。"""
        vacate_asset_slots(game_state, self.instance_id)
        if self.instance_id in inv.play_area:
            inv.play_area.remove(self.instance_id)
        game_state.cards_in_play.pop(self.instance_id, None)
        inv.discard.append(self.card_id)
