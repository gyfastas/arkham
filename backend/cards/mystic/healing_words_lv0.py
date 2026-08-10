"""Healing Words (Level 0) — Mystic Asset, Arcane slot.
使用(3充能)。[action]花费1充能：治愈你所在地点一位调查员的1点伤害。
"""

from backend.cards.base import CardImplementation


class HealingWords(CardImplementation):
    card_id = "healing_words_lv0"
    heal_amount = 1  # lv3 覆盖：共治愈2点，可在同地点调查员间分配
    activations = [{
        "id": "heal",
        "label": "花1充能：治愈同地点调查员伤害",
        "method": "activate",
        "actions": 1,
    }]

    def activate(self, game_state, investigator_id: str,
                 target_investigator_ids: list[str] | None = None) -> bool:
        """花费1充能：治愈同地点调查员共 heal_amount 点伤害。

        target_investigator_ids: lv3 可传多个目标依次各治愈1点（可重复同一目标
        表示集中治愈）；默认全部治愈发动者本人。
        """
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None or inst.uses.get("charges", 0) <= 0:
            return False

        if target_investigator_ids is None:
            targets = [investigator_id] * self.heal_amount
        else:
            targets = list(target_investigator_ids)[: self.heal_amount]
        if not targets:
            return False
        # 校验全部目标合法后再扣充能
        resolved = []
        for tid in targets:
            target = game_state.get_investigator(tid)
            if target is None or target.location_id != inv.location_id:
                return False
            resolved.append(target)
        if not any(t.damage > 0 for t in resolved):
            return False

        inst.uses["charges"] -= 1
        healed = 0
        for target in resolved:
            if target.damage > 0:
                target.damage -= 1
                healed += 1
        return healed > 0
