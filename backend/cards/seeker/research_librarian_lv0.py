"""Research Librarian (Level 0) — Seeker Asset, Ally slot.
进场时从牌库中搜索1张典籍(Tome)支援卡加入手牌，然后洗牌。
"""

import random

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class ResearchLibrarian(CardImplementation):
    card_id = "research_librarian_lv0"

    @on_event(
        GameEvent.CARD_ENTERS_PLAY,
        priority=TimingPriority.REACTION,
    )
    def search_for_tome(self, ctx):
        """When Research Librarian enters play, search deck for a Tome asset."""
        if ctx.target != self.instance_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        # Search deck for a card with "tome" trait
        tome_idx = None
        for i, card_id in enumerate(inv.deck):
            card_def = ctx.game_state.get_card_data(card_id)
            if card_def and "tome" in getattr(card_def, "traits", []):
                tome_idx = i
                break
        msgs = ctx.game_state.scenario.vars.setdefault("action_messages", [])
        if tome_idx is not None:
            tome_card_id = inv.deck.pop(tome_idx)
            cd = ctx.game_state.get_card_data(tome_card_id)
            name = cd.name_cn or cd.name if cd else tome_card_id
            inv.hand.append(tome_card_id)
            random.shuffle(inv.deck)
            msgs.append(f"📚 研究图书馆员：从牌库搜索到《{name}》加入手牌，然后洗牌")
        else:
            msgs.append("📚 研究图书馆员：牌库中没有典籍（Tome）牌")
