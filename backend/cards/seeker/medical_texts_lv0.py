"""Medical Texts (Level 0) — Seeker Asset, Hand slot.
消耗：进行智力(2)检定。成功治疗1点伤害，失败造成1点伤害。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class MedicalTexts(CardImplementation):
    card_id = "medical_texts_lv0"

    def activate(self, ctx, target_id: str | None = None):
        """Exhaust: test Intellect (2). Success: heal 1 damage. Failure: deal 1 damage.

        Skeleton — the actual skill test would be initiated through the
        skill test framework. This method sets up the test parameters.
        """
        inv_id = target_id or ctx.investigator_id
        inv = ctx.game_state.get_investigator(inv_id)
        if inv is None:
            return
        # In full implementation, this would initiate a skill test:
        # ctx.initiate_skill_test(
        #     investigator_id=ctx.investigator_id,
        #     skill=Skill.INTELLECT,
        #     difficulty=2,
        #     source=self.instance_id,
        #     target=inv_id,
        # )
        pass

    @on_event(
        GameEvent.SKILL_TEST_SUCCESSFUL,
        priority=TimingPriority.AFTER,
    )
    def heal_on_success(self, ctx):
        """On successful intellect test from Medical Texts, heal 1 damage."""
        if ctx.source != self.instance_id:
            return
        target_id = ctx.extra.get("target_id", ctx.investigator_id)
        inv = ctx.game_state.get_investigator(target_id)
        if inv and inv.damage > 0:
            inv.damage -= 1

    @on_event(
        GameEvent.SKILL_TEST_FAILED,
        priority=TimingPriority.AFTER,
    )
    def damage_on_failure(self, ctx):
        """On failed intellect test from Medical Texts, deal 1 damage."""
        if ctx.source != self.instance_id:
            return
        target_id = ctx.extra.get("target_id", ctx.investigator_id)
        inv = ctx.game_state.get_investigator(target_id)
        if inv:
            inv.damage += 1
