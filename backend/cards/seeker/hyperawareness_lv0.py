"""Hyperawareness (Level 0) — Seeker Asset.
花费1资源获得+1智力或+1敏捷（技能检定期间）。
"""

from backend.cards.base import CardImplementation
from backend.models.enums import Skill


class Hyperawareness(CardImplementation):
    card_id = "hyperawareness_lv0"

    # Hyperawareness is a player-activated ability during skill tests.
    # It requires spending 1 resource for +1 to Intellect or Agility.
    # This cannot be auto-triggered — it requires player choice input.
    # The action system should call boost() when the player decides to use it.

    def boost(self, ctx, skill: Skill) -> bool:
        """Spend 1 resource to gain +1 to the chosen skill.

        Returns True if the boost was applied, False if not enough resources
        or invalid skill type.
        """
        if skill not in (Skill.INTELLECT, Skill.AGILITY):
            return False
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or inv.resources < 1:
            return False
        if self.instance_id not in inv.play_area:
            return False
        inv.resources -= 1
        label = f"hyperawareness_{skill.value}_boost"
        ctx.modify_amount(1, label)
        return True
