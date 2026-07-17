"""罗兰的.38特种手枪（Roland's .38 Special）— 罗兰·班克斯专属支援卡，武器。
使用（4弹药）。
[行动]花费1弹药：战斗。该次攻击+1战斗（若你所在地点有1个或以上线索，
改为+3战斗），造成+1伤害。

简化说明：弹药消耗在命中（造成伤害）时扣除，与 .45自动手枪 的实现保持一致；
弹药耗尽后攻击不再获得加值。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class Rolands38Special(CardImplementation):
    card_id = "rolands_38_special"

    @on_event(
        GameEvent.SKILL_VALUE_DETERMINED,
        priority=TimingPriority.WHEN,
    )
    def combat_bonus(self, ctx):
        """+1 Combat (+3 instead if 1+ clues at your location) when fighting
        with this weapon (requires ammo)."""
        if ctx.source != self.instance_id:
            return
        if ctx.skill_type != Skill.COMBAT:
            return
        card = ctx.game_state.get_card_instance(self.instance_id)
        if card is None or card.uses.get("ammo", 0) <= 0:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        bonus = 1
        if inv is not None:
            location = ctx.game_state.get_location(inv.location_id)
            if location is not None and location.clues >= 1:
                bonus = 3
        ctx.modify_amount(bonus, "rolands_38_combat_bonus")

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
            ctx.modify_amount(1, "rolands_38_extra_damage")
