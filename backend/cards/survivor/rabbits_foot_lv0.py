"""Rabbit's Foot (Level 0) — Survivor Asset, Accessory slot.
[reaction] After you fail a skill test, exhaust Rabbit's Foot: Draw 1 card.
（横置后每轮至多触发一次——刷新阶段重置。）
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
        """After you fail a skill test, exhaust Rabbit's Foot: Draw 1 card."""
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None or inst.exhausted or not inv.deck:
            return
        inst.exhausted = True
        inv.hand.append(inv.deck.pop(0))
        ctx.game_state.log_effect("🐇 幸运兔脚：横置，抽1张牌")
