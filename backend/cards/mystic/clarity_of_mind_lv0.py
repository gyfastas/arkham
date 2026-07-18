"""Clarity of Mind (Level 0) — Mystic Asset, Arcane slot.
使用(3充能)。[action]花费1充能：治愈你所在地点一位调查员1点恐惧。
"""

from backend.cards.base import CardImplementation


class ClarityOfMind(CardImplementation):
    card_id = "clarity_of_mind_lv0"

    def activate(self, game_state, investigator_id: str,
                 target_investigator_id: str | None = None) -> bool:
        """花费1充能：治愈目标1点恐惧（默认自己）。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None or inst.uses.get("charges", 0) <= 0:
            return False

        target_id = target_investigator_id or investigator_id
        target = game_state.get_investigator(target_id)
        if target is None or target.horror <= 0:
            return False
        if target.location_id != inv.location_id:
            return False

        inst.uses["charges"] -= 1
        target.horror -= 1
        return True
