"""Stray Cat (Level 0) — Survivor Asset, Ally slot.
[fast] Discard Stray Cat: Automatically evade a non-Elite enemy at your location.

简化说明：
- 自动躲避=横置+脱离交战并留在当前地点，不触发 ENEMY_EVADED 事件（从简）。
"""

from backend.cards.base import CardImplementation
from backend.engine.slots import vacate_asset_slots
from backend.scenarios.official_core import is_elite_enemy


class StrayCat(CardImplementation):
    card_id = "stray_cat_lv0"
    activations = [{
        "id": "evade", "label": "快速：弃置野猫自动躲避", "method": "activate",
        "target": "enemy", "actions": 0,
    }]

    def _is_at_location(self, game_state, location_id, enemy_instance_id) -> bool:
        """敌人在该地点：未交战（地点敌人列表）或与当地点任一调查员交战。"""
        loc = game_state.get_location(location_id)
        if loc is not None and enemy_instance_id in loc.enemies:
            return True
        for inv in game_state.investigators.values():
            if inv.location_id == location_id and enemy_instance_id in inv.threat_area:
                return True
        return False

    def activate(self, game_state, investigator_id: str, enemy_instance_id: str) -> bool:
        """弃置野猫：自动躲避你所在地点的一个非精英敌人。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return False
        enemy = game_state.get_card_instance(enemy_instance_id)
        if enemy is None:
            return False
        if not self._is_at_location(game_state, inv.location_id, enemy_instance_id):
            return False
        cd = game_state.get_card_data(enemy.card_id)
        if cd is not None and is_elite_enemy(cd):
            return False

        # 弃置野猫
        vacate_asset_slots(game_state, self.instance_id)
        if self.instance_id in inv.play_area:
            inv.play_area.remove(self.instance_id)
        game_state.cards_in_play.pop(self.instance_id, None)
        inv.discard.append("stray_cat_lv0")

        # 自动躲避：横置并脱离交战，留在当前地点
        enemy.exhausted = True
        for other in game_state.investigators.values():
            if enemy_instance_id in other.threat_area:
                other.threat_area.remove(enemy_instance_id)
        loc = game_state.get_location(inv.location_id)
        if loc is not None and enemy_instance_id not in loc.enemies:
            loc.enemies.append(enemy_instance_id)
        return True
