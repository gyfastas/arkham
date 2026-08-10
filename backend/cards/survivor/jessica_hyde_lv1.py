"""Jessica Hyde (Level 1) — Survivor Asset, Ally slot. (06118)
You get +1 [combat].
Jessica Hyde enters play with 2 damage on her.
[reaction] After your turn ends: Heal 1 damage from Jessica Hyde.
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class JessicaHyde(CardImplementation):
    card_id = "jessica_hyde_lv1"

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def combat_bonus(self, ctx):
        """+1 Combat while Jessica Hyde is in play."""
        if ctx.skill_type != Skill.COMBAT:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv and self.instance_id in inv.play_area:
            ctx.modify_amount(1, "jessica_hyde_combat")

    @on_event(GameEvent.CARD_ENTERS_PLAY, priority=TimingPriority.AFTER)
    def enters_with_damage(self, ctx):
        """杰西卡·海德入场时自带2点伤害。"""
        if ctx.target != self.instance_id:
            return
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is not None:
            inst.damage += 2

    @on_event(GameEvent.INVESTIGATOR_TURN_ENDS, priority=TimingPriority.AFTER)
    def heal_damage(self, ctx):
        """你的回合结束后：治愈杰西卡·海德1点伤害。"""
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is not None and inst.damage > 0:
            inst.damage -= 1
