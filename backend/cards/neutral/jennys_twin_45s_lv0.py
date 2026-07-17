"""珍妮的.45双枪（Jenny's Twin .45s，Level 0）— 珍妮·巴恩斯专属支援卡，武器（双手）。
使用（X弹药，按FAQ X=4）。
[行动]花费1弹药：攻击。该次攻击+2战斗，造成+1伤害。

简化说明：弹药消耗在命中（造成伤害）时扣除，与 .45自动手枪 的实现保持一致；
弹药耗尽后攻击不再获得加值。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class JennysTwin45s(CardImplementation):
    card_id = "jennys_twin_45s_lv0"

    @on_event(
        GameEvent.SKILL_VALUE_DETERMINED,
        priority=TimingPriority.WHEN,
    )
    def combat_bonus(self, ctx):
        """+2 Combat when fighting with this weapon (requires ammo)."""
        if ctx.source != self.instance_id:
            return
        if ctx.skill_type != Skill.COMBAT:
            return
        card = ctx.game_state.get_card_instance(self.instance_id)
        if card is None or card.uses.get("ammo", 0) <= 0:
            return
        ctx.modify_amount(2, "jennys_twin_45s_combat_bonus")

    @on_event(
        GameEvent.DAMAGE_DEALT,
        priority=TimingPriority.WHEN,
    )
    def extra_damage(self, ctx):
        """+1 damage when attacking with this weapon; spends 1 ammo."""
        if ctx.source != self.instance_id:
            return
        card = ctx.game_state.get_card_instance(self.instance_id)
        if card and card.uses.get("ammo", 0) > 0:
            card.uses["ammo"] -= 1
            ctx.modify_amount(1, "jennys_twin_45s_extra_damage")
