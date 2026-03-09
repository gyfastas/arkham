"""Rabbit's Foot (Level 0) — Survivor Asset, Accessory slot.
幸运兔脚。技能检定失败后，疲倦此卡：抽1张牌。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class RabbitsFoot(CardImplementation):
    card_id = "rabbits_foot_lv0"

    @on_event(
        GameEvent.SKILL_TEST_FAILED,
        priority=TimingPriority.REACTION,
    )
    def draw_on_fail(self, ctx):
        """After you fail a skill test, exhaust: Draw 1 card."""
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv and self.instance_id in inv.play_area and inv.deck:
            inv.hand.append(inv.deck.pop(0))
