"""Word of Command (Level 2) — Mystic Event. (06202)
声名一张[[法术]]卡牌。在你的牌堆中查找并抽取1张声名的卡牌。混洗你的牌堆。

简化说明：
- "声名一张法术卡"需要选择 UI，简化为自动选牌堆中第一张带 spell 特质的卡。
"""

import random

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class WordOfCommand(CardImplementation):
    card_id = "word_of_command_lv2"

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def search_spell(self, ctx):
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        found_idx = None
        for idx, deck_card_id in enumerate(inv.deck):
            cd = ctx.game_state.get_card_data(deck_card_id)
            if cd is not None and "spell" in (cd.traits or []):
                found_idx = idx
                break
        if found_idx is None:
            ctx.game_state.log_effect("📜 命令真言：牌堆中没有法术卡")
            random.shuffle(inv.deck)
            return
        card_id = inv.deck.pop(found_idx)
        inv.hand.append(card_id)
        random.shuffle(inv.deck)
        ctx.extra["word_of_command_drawn"] = card_id
        ctx.game_state.log_effect(
            f"📜 命令真言：从牌堆抽取【{ctx.game_state.card_name(card_id)}】并混洗")
