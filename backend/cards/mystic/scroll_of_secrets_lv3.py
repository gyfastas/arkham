"""Scroll of Secrets (Level 3) — Mystic Asset, Hand slot (Tome).
使用(4秘密)。[action]横置秘密卷轴并花费1秘密：查看任一调查员牌库或遭遇牌堆
顶/底的1张牌。然后：弃掉它、加入其拥有者手牌、放到其牌库底、或放到其牌库顶。

简化说明：
- 处置方式经 mode 参数指定（"top"/"bottom"/"discard"/"hand"），默认 "top"
  （原样放回顶，无操作）。"hand" 仅对调查员牌库可用（遭遇牌无拥有者手牌）。
"""

from backend.cards.base import CardImplementation


class ScrollOfSecretsLv3(CardImplementation):
    card_id = "scroll_of_secrets_lv3"
    activations = [{
        "id": "peek",
        "label": "横置+1秘密：查看任一牌库顶/底并处置",
        "method": "activate",
        "actions": 1,
    }]

    def activate(self, game_state, investigator_id: str,
                 target_investigator_id: str | None = None,
                 target_encounter_deck: bool = False,
                 from_bottom: bool = False,
                 mode: str = "top") -> str | bool:
        """横置并花费1秘密：查看并处置目标牌堆顶/底的1张牌。

        返回查看到的 card_id；失败返回 False。
        """
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None or inst.exhausted or inst.uses.get("secrets", 0) <= 0:
            return False

        owner = None
        if target_encounter_deck:
            deck = game_state.scenario.encounter_deck
        else:
            owner = game_state.get_investigator(target_investigator_id or investigator_id)
            if owner is None:
                return False
            deck = owner.deck
        if not deck:
            return False
        if mode == "hand" and owner is None:
            return False  # 遭遇牌无法加入拥有者手牌

        inst.uses["secrets"] -= 1
        inst.exhausted = True

        idx = -1 if from_bottom else 0
        card_id = deck[idx]

        if mode == "discard":
            deck.pop(idx)
            if owner is not None:
                owner.discard.append(card_id)
            else:
                game_state.scenario.encounter_discard.append(card_id)
        elif mode == "hand":
            deck.pop(idx)
            owner.hand.append(card_id)
        elif mode == "bottom" and not from_bottom:
            deck.append(deck.pop(0))
        elif mode == "top" and from_bottom:
            deck.insert(0, deck.pop())
        # 其余情况（mode 与查看端一致）：原样放回，无操作
        return card_id
