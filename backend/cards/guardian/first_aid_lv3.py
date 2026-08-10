"""First Aid (Level 3) — Guardian Asset.
使用(4补给)。如果急救没有补给，弃置它。
[行动]花费1补给：治愈你所在地点的一名调查员或盟友的1点伤害和1点恐惧。

简化说明：
- 目标默认为自己；会话层可传 target_investigator_id（同地点调查员）
  或 target_instance_id（同地点调查员控制的盟友）。
- 目标只需有伤害或恐惧其一即可启动（治愈存在的各项至多1点）。
"""

from backend.cards.base import CardImplementation
from backend.cards.guardian.first_aid_lv0 import FirstAid


class FirstAidLv3(FirstAid):
    card_id = "first_aid_lv3"
    activations = [{"id": "heal", "label": "花1补给：治愈1伤害和1恐惧", "method": "activate"}]

    def activate(self, game_state, investigator_id: str,
                 target_investigator_id: str | None = None,
                 target_instance_id: str | None = None) -> bool:
        """花费1补给：治愈目标1点伤害和1点恐惧。"""
        inv = game_state.get_investigator(investigator_id)
        inst = game_state.get_card_instance(self.instance_id)
        if inv is None or inst is None:
            return False
        if self.instance_id not in inv.play_area:
            return False
        if inst.uses.get(self.supplies_key, 0) <= 0:
            return False

        # 解析目标：调查员或盟友，必须与使用者同地点
        if target_instance_id is not None:
            target = self._ally_at_location(game_state, target_instance_id,
                                            inv.location_id)
            if target is None:
                return False
        else:
            target = game_state.get_investigator(target_investigator_id or investigator_id)
            if target is None or target.location_id != inv.location_id:
                return False

        healed_damage = target.damage > 0
        healed_horror = target.horror > 0
        if not (healed_damage or healed_horror):
            return False
        if healed_damage:
            target.damage -= 1
        if healed_horror:
            target.horror -= 1

        inst.uses[self.supplies_key] -= 1
        if inst.uses[self.supplies_key] <= 0:
            self._discard_self(game_state, inv)
        return True

    @staticmethod
    def _ally_at_location(game_state, instance_id: str, location_id: str):
        """返回盟友实例：须在同地点某位调查员的装备区且有生命/理智。"""
        ally = game_state.get_card_instance(instance_id)
        if ally is None:
            return None
        data = game_state.get_card_data(ally.card_id)
        if data is None or (data.health is None and data.sanity is None):
            return None
        owner = game_state.get_investigator(ally.controller_id)
        if owner is None or owner.location_id != location_id:
            return None
        if instance_id not in owner.play_area:
            return None
        return ally
