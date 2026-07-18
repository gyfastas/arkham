"""First Aid (Level 0) — Guardian Asset.
消耗急救并花费1资源：治愈你所在地点的一名调查员或盟友2点伤害。
"""

from backend.cards.base import CardImplementation


class FirstAid(CardImplementation):
    card_id = "first_aid_lv0"
    heal_amount = 2

    def activate(self, game_state, investigator_id: str,
                 target_instance_id: str | None = None) -> bool:
        """消耗+1资源：治愈目标2点伤害（默认治愈自己）。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or inv.resources < 1:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None or inst.exhausted:
            return False

        if target_instance_id is None:
            if inv.damage <= 0:
                return False
            inv.damage = max(0, inv.damage - self.heal_amount)
        else:
            target = game_state.get_card_instance(target_instance_id)
            if target is None or target.damage <= 0:
                return False
            target.damage = max(0, target.damage - self.heal_amount)

        inv.resources -= 1
        inst.exhausted = True
        return True
