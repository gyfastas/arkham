"""Bait and Switch (Level 0) — Survivor Event.
躲避。如果成功并且该敌人为非[精英]，躲避并将该敌人移动到一个连接地点。

简化说明：
- 躲避检定由会话层发起；成功后调用 resolve(enemy_instance_id) 完成
  躲避与移动（移动目标简化为第一个连接地点，或经 destination 指定）。
"""

from backend.cards.base import CardImplementation


class BaitAndSwitch(CardImplementation):
    card_id = "bait_and_switch_lv0"

    @staticmethod
    def resolve(game_state, investigator_id: str, enemy_instance_id: str,
                destination: str | None = None) -> bool:
        inv = game_state.get_investigator(investigator_id)
        enemy = game_state.get_card_instance(enemy_instance_id)
        if inv is None or enemy is None:
            return False
        enemy_data = game_state.get_card_data(enemy.card_id)
        if enemy_data is not None and "elite" in (getattr(enemy_data, "traits", []) or []):
            return False

        # 躲避：横置并脱离交战
        enemy.exhausted = True
        if enemy_instance_id in inv.threat_area:
            inv.threat_area.remove(enemy_instance_id)

        # 移动到连接地点
        current_loc = game_state.get_location(inv.location_id)
        if current_loc is None:
            return False
        connections = getattr(current_loc, "connections", []) or []
        target = destination or (connections[0] if connections else None)
        if target is None or target not in game_state.locations:
            return False
        if enemy_instance_id in current_loc.enemies:
            current_loc.enemies.remove(enemy_instance_id)
        game_state.locations[target].enemies.append(enemy_instance_id)
        enemy.attached_to = target
        return True
