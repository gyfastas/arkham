"""Beat Cop (Level 0) — Guardian Asset, Ally slot.
+1战斗力。弃置巡警：对你所在地点的一个敌人造成1点伤害。
"""
from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class BeatCop(CardImplementation):
    card_id = "beat_cop_lv0"
    activations = [{
        "id": "discard_damage",
        "label": "弃置巡警：对交战敌人造成1伤害",
        "method": "activate_discard_damage",
        "target": "enemy",
        "actions": 0,
        "resource_cost": 0,
        "timing": "combat",
    }]

    def activate_discard_damage(self, game_state, investigator_id: str,
                                enemy_instance_id: str) -> bool:
        inv = game_state.get_investigator(investigator_id)
        enemy = game_state.get_card_instance(enemy_instance_id)
        if inv is None or enemy is None or self.instance_id not in inv.play_area:
            return False
        if enemy_instance_id not in inv.threat_area:
            return False
        manager = getattr(game_state, "slot_managers", {}).get(investigator_id)
        if manager:
            manager.vacate(self.instance_id)
        inv.play_area.remove(self.instance_id)
        inv.discard.append(self.card_id)
        game_state.cards_in_play.pop(self.instance_id, None)
        enemy.damage += 1
        return True

    @on_event(
        GameEvent.SKILL_VALUE_DETERMINED,
        priority=TimingPriority.WHEN,
    )
    def combat_bonus(self, ctx):
        """+1 Combat while Beat Cop is in play."""
        if ctx.skill_type == Skill.COMBAT:
            inv = ctx.game_state.get_investigator(ctx.investigator_id)
            if inv and self.instance_id in inv.play_area:
                ctx.modify_amount(1, "beat_cop_combat_bonus")
