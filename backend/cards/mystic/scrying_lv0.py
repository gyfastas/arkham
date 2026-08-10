"""Scrying (Level 0) — Mystic Asset, Arcane slot. (01061)
使用(3充能)。
[action] 横置探知术并花费1充能：查看任意一名调查员的牌库或遭遇牌堆顶的3张牌。
将它们以任意顺序放回该牌堆顶。

简化说明：
- 无重排选择 UI：默认保持原顺序放回顶；调用方可传 order（顶3张的新顺序索引）
  以支持会话层/UI 重排。
"""

from backend.cards.base import CardImplementation


class Scrying(CardImplementation):
    card_id = "scrying_lv0"
    look_count = 3
    horror_on_terror_or_omen = False  # lv3：查到 Terror/Omen 卡受1恐惧
    activations = [{
        "id": "scry",
        "label": "横置+1充能：查看任一牌库或遭遇牌堆顶3张",
        "method": "activate",
        "actions": 1,
    }]

    def activate(self, game_state, investigator_id: str,
                 target_investigator_id: str | None = None,
                 target_encounter_deck: bool = False,
                 order: list[int] | None = None) -> bool:
        """横置并花费1充能：查看目标牌堆顶3张，以任意顺序放回顶。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None or inst.exhausted or inst.uses.get("charges", 0) <= 0:
            return False

        if target_encounter_deck:
            deck = game_state.scenario.encounter_deck
            owner = None
        else:
            owner = game_state.get_investigator(target_investigator_id or investigator_id)
            if owner is None:
                return False
            deck = owner.deck
        if not deck:
            return False

        inst.uses["charges"] -= 1
        inst.exhausted = True

        n = min(self.look_count, len(deck))
        top = deck[:n]
        # 重排：order 为 top 的新顺序索引（简化：默认保持原顺序）
        if order and sorted(order) == list(range(n)):
            new_top = [top[i] for i in order]
        else:
            new_top = top
        deck[:n] = new_top

        # lv3：查看的牌中有 Terror 或 Omen 卡时，受1恐惧
        if self.horror_on_terror_or_omen:
            for card_id in top:
                cd = game_state.get_card_data(card_id)
                traits = [t.lower() for t in (cd.traits or [])] if cd else []
                if "terror" in traits or "omen" in traits:
                    inv.horror += 1
                    break
        return True
