"""Burglary (Level 0) — Rogue Asset.
调查。使用敏捷代替智力。如果你成功，获得3资源而不是发现线索。

简化说明：
- activate() 武装；随后由会话层发起调查行动。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class Burglary(CardImplementation):
    card_id = "burglary_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._armed = False

    def activate(self, game_state, investigator_id: str) -> bool:
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        self._armed = True
        return True

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def substitute_agility(self, ctx):
        if not self._armed or ctx.skill_type != Skill.INTELLECT:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        agility = inv.get_skill(Skill.AGILITY)
        ctx.modify_amount(agility - ctx.amount, "burglary_substitute")

    @on_event(GameEvent.CLUE_DISCOVERED, priority=TimingPriority.WHEN)
    def resources_instead(self, ctx):
        """成功：获得3资源而不是发现线索（事后校正）。"""
        if not self._armed:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        loc = ctx.game_state.get_location(ctx.location_id or inv.location_id)
        if loc is not None:
            loc.clues += 1  # 返还线索
        inv.clues = max(0, inv.clues - 1)
        inv.resources += 3
        ctx.extra["burglary_resources"] = True

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._armed = False
