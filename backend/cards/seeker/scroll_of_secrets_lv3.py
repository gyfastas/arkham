"""Scroll of Secrets (Level 3) — Seeker Asset, Hand slot. (05188)
使用(3秘密)。
[行动]消耗秘密卷轴并花费1秘密：查看任意一位调查员牌堆或遭遇牌堆底部
的3张卡牌。你可以丢弃其中1张。你可以将其中1张加入其所有者的手牌。
将其中剩余的卡牌以任意顺序放到该牌堆底部或者顶部。

简化说明：
- 目标牌堆：target_investigator_id 指定调查员，target_encounter_deck=True
  指定遭遇牌堆（缺省为你自己的牌堆）；
- 处置参数（均为被查看的3张牌中的下标，0=最底部）：
  discard_index 丢弃1张（None=不丢）、hand_index 加入所有者手牌
  （None=不加；遭遇牌堆不可用）、placement="bottom"（默认，其余按原顺序
  放回底部）/"top"（其余按原顺序放顶部）；
- 数据 JSON 中 uses 键为 "secretss"（上游笔误），读取时兼容两种键名。
"""

from backend.cards.base import CardImplementation


def _secrets(inst) -> str:
    return "secretss" if "secretss" in inst.uses else "secrets"


class ScrollOfSecretsLv3(CardImplementation):
    card_id = "scroll_of_secrets_lv3"
    activations = [{
        "id": "scry_bottom3",
        "label": "[行动]消耗+1秘密：查看任一牌堆底3张并处置",
        "method": "activate",
        "actions": 1,
    }]

    def activate(self, game_state, investigator_id: str,
                 target_investigator_id: str | None = None,
                 target_encounter_deck: bool = False,
                 discard_index: int | None = None,
                 hand_index: int | None = None,
                 placement: str = "bottom") -> bool:
        """消耗+1秘密：查看目标牌堆底3张，可弃1张、入手1张，其余放顶/底。"""
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
        if placement not in ("bottom", "top"):
            return False

        n = min(3, len(deck))
        looked = deck[-n:]  # 底部n张，保持顺序（末尾=最底部）

        used = {i for i in (discard_index, hand_index) if i is not None}
        if len(used) != len([i for i in (discard_index, hand_index) if i is not None]):
            return False  # 同一张牌不能既丢弃又入手
        if any(i < 0 or i >= n for i in used):
            return False
        if hand_index is not None and owner is None:
            return False  # 遭遇牌堆的牌无法加入手牌

        inst.exhausted = True
        inst.uses[key] -= 1

        del deck[-n:]  # 取出底部n张
        rest = []
        for i, card_id in enumerate(looked):
            if i == discard_index:
                if owner is not None:
                    owner.discard.append(card_id)
                else:
                    game_state.scenario.encounter_discard.append(card_id)
            elif i == hand_index:
                owner.hand.append(card_id)
            else:
                rest.append(card_id)
        if placement == "top":
            deck[0:0] = rest
        else:
            deck.extend(rest)

        game_state.log_effect(
            f"📜 秘密卷轴：查看底部{n}张（弃{discard_index}、入手"
            f"{hand_index}），其余放回{placement}")
        return True
