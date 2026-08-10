"""Scroll of Secrets (Level 0) — Seeker Asset, Hand slot. (05116)
使用(3秘密)。
[行动]消耗秘密卷轴并花费1秘密：查看遭遇牌堆或任意一位调查员牌堆底部
的卡牌。然后，丢弃该卡牌、将其加入其所有者手牌，或将其放到该牌堆
顶部或牌堆底部。

简化说明：
- 目标牌堆：target_investigator_id 指定调查员，target_encounter_deck=True
  指定遭遇牌堆（缺省为你自己的牌堆）；
- 处置由 disposition 指定："bottom"（默认，放回原处）/"top"/"discard"/
  "hand"（"hand"仅调查员牌堆可用——遭遇牌堆的牌没有所有者手牌）；
- 数据 JSON 中 uses 键为 "secretss"（上游笔误），读取时兼容两种键名。
"""

from backend.cards.base import CardImplementation


def _secrets(inst) -> str:
    return "secretss" if "secretss" in inst.uses else "secrets"


class ScrollOfSecrets(CardImplementation):
    card_id = "scroll_of_secrets_lv0"
    activations = [{
        "id": "scry_bottom",
        "label": "[行动]消耗+1秘密：查看任一牌堆/遭遇牌堆底牌并处置",
        "method": "activate",
        "actions": 1,
    }]

    def activate(self, game_state, investigator_id: str,
                 target_investigator_id: str | None = None,
                 target_encounter_deck: bool = False,
                 disposition: str = "bottom") -> bool:
        """消耗+1秘密：查看目标牌堆底牌，按 disposition 处置。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None or inst.exhausted:
            return False
        key = _secrets(inst)
        if inst.uses.get(key, 0) <= 0:
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
        if disposition == "hand" and owner is None:
            return False  # 遭遇牌堆的牌无法加入手牌
        if disposition not in ("bottom", "top", "discard", "hand"):
            return False

        inst.exhausted = True
        inst.uses[key] -= 1

        card_id = deck[-1]  # 查看底牌
        if disposition != "bottom":
            deck.pop()
            if disposition == "top":
                deck.insert(0, card_id)
            elif disposition == "discard":
                if owner is not None:
                    owner.discard.append(card_id)
                else:
                    game_state.scenario.encounter_discard.append(card_id)
            elif disposition == "hand":
                owner.hand.append(card_id)

        game_state.log_effect(
            f"📜 秘密卷轴：查看底牌【{game_state.card_name(card_id)}】，"
            f"处置：{disposition}")
        return True
