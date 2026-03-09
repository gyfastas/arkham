"""Leo De Luca (Level 1) — Rogue Asset.
里奥·德·卢卡（升级版）。费用降低，效果同lv0：你的回合中可以执行额外1个行动。
"""
from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class LeoDeLucaLv1(CardImplementation):
    card_id = "leo_de_luca_lv1"

    @on_event(GameEvent.INVESTIGATION_PHASE_BEGINS, priority=TimingPriority.WHEN)
    def grant_action(self, ctx):
        """Grant 1 additional action at the start of the investigation phase."""
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv and self.instance_id in inv.play_area:
            inv.actions_remaining += 1
