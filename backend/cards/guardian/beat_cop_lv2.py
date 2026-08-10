"""Beat Cop (Level 2) — Guardian Asset, Ally slot.
你获得+1战斗。
[快速]横置巡警并对它造成1点伤害：对你所在地点的一名敌人造成1点伤害。
"""
from backend.cards.base import CardImplementation, on_event
from backend.cards.guardian.beat_cop_lv0 import _enemy_at_location
from backend.models.enums import GameEvent, Skill, TimingPriority


class BeatCopLv2(CardImplementation):
    card_id = "beat_cop_lv2"
    activations = [{
        "id": "exhaust_damage",
        "label": "横置巡警+自伤1：对同地点敌人造成1伤害",
        "method": "activate_exhaust_damage",
        "target": "enemy",
        "actions": 0,
        "resource_cost": 0,
    }]

    def activate_exhaust_damage(self, game_state, investigator_id: str,
                                enemy_instance_id: str) -> bool:
        inv = game_state.get_investigator(investigator_id)
        enemy = game_state.get_card_instance(enemy_instance_id)
        cop = game_state.get_card_instance(self.instance_id)
        if inv is None or enemy is None or cop is None:
            return False
        if self.instance_id not in inv.play_area or cop.exhausted:
            return False
        if not _enemy_at_location(game_state, inv, enemy_instance_id):
            return False

        cop.exhausted = True
        cop.damage += 1
        enemy.damage += 1

        # 自伤可能击败巡警（累积伤害达到生命值）
        cop_data = game_state.get_card_data(self.card_id)
        if cop_data is not None and cop_data.health is not None \
                and cop.damage >= cop_data.health:
            manager = getattr(game_state, "slot_managers", {}).get(investigator_id)
            if manager:
                manager.vacate(self.instance_id)
            inv.play_area.remove(self.instance_id)
            inv.discard.append(self.card_id)
            game_state.cards_in_play.pop(self.instance_id, None)
        return True

    @on_event(
        GameEvent.SKILL_VALUE_DETERMINED,
        priority=TimingPriority.WHEN,
    )
    def combat_bonus(self, ctx):
        """+1 Combat while Beat Cop (2) is in play."""
        if ctx.skill_type == Skill.COMBAT:
            inv = ctx.game_state.get_investigator(ctx.investigator_id)
            if inv and self.instance_id in inv.play_area:
                ctx.modify_amount(1, "beat_cop_lv2_combat_bonus")
