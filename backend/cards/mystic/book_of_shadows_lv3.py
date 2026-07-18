"""Book of Shadows (Level 3) — Mystic Asset, Hand slot.
你每控制一张法术支援卡，你获得+1意志和+1智力。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import CardType, GameEvent, Skill, TimingPriority


class BookOfShadows(CardImplementation):
    card_id = "book_of_shadows_lv3"

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def spell_count_bonus(self, ctx):
        if ctx.skill_type not in (Skill.WILLPOWER, Skill.INTELLECT):
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        count = 0
        for iid in inv.play_area:
            inst = ctx.game_state.get_card_instance(iid)
            if inst is None:
                continue
            cd = ctx.game_state.get_card_data(inst.card_id)
            if cd is not None and cd.type == CardType.ASSET and "spell" in (cd.traits or []):
                count += 1
        if count > 0:
            ctx.modify_amount(count, "book_of_shadows_spell_count")
