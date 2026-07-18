"""Shared base for "spend 1 resource: +1 <skill> this test" assets.

Used by: Physical Training, Arcane Studies, Hard Knocks, Dig Deep, Hyperawareness.

The boost is armed via `spend()` (called by session/UI when the player chooses
to pay), and applies to the next SKILL_VALUE_DETERMINED of the matching skill
within the current test.
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class ResourceSkillBoost(CardImplementation):
    """子类声明 boosted_skills: 该卡可花资源提升的技能列表。"""

    card_id = ""
    boosted_skills: tuple[Skill, ...] = ()

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._armed_skill: Skill | None = None

    def spend(self, game_state, investigator_id: str, skill: Skill) -> bool:
        """花费1资源：本次技能检定 +1 对应技能。"""
        if skill not in self.boosted_skills:
            return False
        inv = game_state.get_investigator(investigator_id)
        if inv is None or inv.resources < 1:
            return False
        if self.instance_id not in inv.play_area:
            return False
        inv.resources -= 1
        self._armed_skill = skill
        return True

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def apply_boost(self, ctx):
        if self._armed_skill is None or ctx.skill_type != self._armed_skill:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        ctx.modify_amount(1, f"{self.card_id}_boost")
        self._armed_skill = None

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        # 未消耗的武装状态在检定结束后清除（资源已花不退）
        self._armed_skill = None
