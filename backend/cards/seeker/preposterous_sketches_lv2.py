"""Preposterous Sketches (Level 2) — Seeker Event.
只能在你所在地点有线索时打出。抽取3张卡牌。
（打出条件由会话层在打出前校验。）
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class PreposterousSketchesLv2(CardImplementation):
    card_id = "preposterous_sketches_lv2"

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def draw_three_cards(self, ctx):
        if ctx.extra.get("card_id") != "preposterous_sketches_lv2":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        drawn = []
        for _ in range(3):
            if inv.deck:
                cid = inv.deck.pop(0)
                inv.hand.append(cid)
                drawn.append(ctx.game_state.card_name(cid))
        if drawn:
            ctx.game_state.log_effect(f"📥 荒唐的素描：抽到【{'】【'.join(drawn)}】")
