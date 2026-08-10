"""Arcane Initiate (Level 0) — Mystic Asset, Ally slot. (01063)
<b>强制</b> - 在新晋术士进场后：在其上放置1个毁灭标记。
[fast] 横置新晋术士：搜索你牌库顶的3张牌，从中选择1张[[法术]]卡抽取，然后洗混你的牌库。

简化说明：
- 搜索只命中牌库顶3张中的第一张法术卡（无选择 UI）；未命中则仅洗牌。
"""

import random

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class ArcaneInitiate(CardImplementation):
    card_id = "arcane_initiate_lv0"
    activations = [{
        "id": "search_spell",
        "label": "【快速】横置：搜牌库顶3张找1张法术并抽取，然后洗牌",
        "method": "activate",
    }]

    @on_event(GameEvent.CARD_ENTERS_PLAY, priority=TimingPriority.AFTER)
    def enter_play(self, ctx):
        """强制 - 进场后：在其上放置1个毁灭标记。"""
        if ctx.target != self.instance_id:
            return
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None:
            return
        inst.doom += 1
        ctx.extra["arcane_initiate_doom"] = True

    def activate(self, game_state, investigator_id: str) -> bool:
        """【快速】横置：搜索牌库顶3张牌中的1张法术卡并抽取，然后洗牌。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None or inst.exhausted:
            return False
        inst.exhausted = True

        top = inv.deck[:3]
        found = None
        for i, card_id in enumerate(top):
            cd = game_state.get_card_data(card_id)
            if cd is not None and "spell" in (cd.traits or []):
                found = inv.deck.pop(i)
                inv.hand.append(found)
                break
        random.shuffle(inv.deck)
        if found:
            game_state.log_effect(
                f"🔮 新晋术士：搜索牌库顶3张，抽取【{game_state.card_name(found)}】")
        return True
