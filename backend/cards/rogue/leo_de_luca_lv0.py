"""Leo De Luca (Level 0) — Rogue Asset.
里奥·德·卢卡。你的回��中可���执行额外1个行动。
"""
from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class LeoDeLuca(CardImplementation):
    card_id = "leo_de_luca_lv0"

    @on_event(GameEvent.INVESTIGATION_PHASE_BEGINS, priority=TimingPriority.WHEN)
    def grant_action(self, ctx):
        """Grant 1 additional action at the start of the investigation phase."""
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv and self.instance_id in inv.play_area:
            inv.actions_remaining += 1
