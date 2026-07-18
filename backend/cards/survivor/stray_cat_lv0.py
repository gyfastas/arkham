"""Stray Cat (Level 0) — Survivor Asset, Ally slot.
快速。弃置野猫：自动成功躲避一个与你交战的非精英敌人。
"""

from backend.cards.base import CardImplementation


class StrayCat(CardImplementation):
    card_id = "stray_cat_lv0"
    activations = [{"id": "evade", "label": "快速：弃置野猫自动躲避", "method": "activate", "target": "enemy"}]

    def activate(self, game_state, investigator_id: str, enemy_instance_id: str) -> bool:
        """弃置野猫：自动成功躲避一个交战的非精英敌人。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return False
        if enemy_instance_id not in inv.threat_area:
            return False
        enemy = game_state.get_card_instance(enemy_instance_id)
        if enemy is None:
            return False
        cd = game_state.get_card_data(enemy.card_id)
        if cd is not None and "elite" in (cd.traits or []):
            return False

        # 弃置野猫
        if self.instance_id in inv.play_area:
            inv.play_area.remove(self.instance_id)
        game_state.cards_in_play.pop(self.instance_id, None)
        inv.discard.append("stray_cat_lv0")

        # 自动成功躲避：横置并脱离交战，放回当前地点
        enemy.exhausted = True
        inv.threat_area.remove(enemy_instance_id)
        loc = game_state.get_location(inv.location_id)
        if loc is not None and enemy_instance_id not in loc.enemies:
            loc.enemies.append(enemy_instance_id)
        return True
