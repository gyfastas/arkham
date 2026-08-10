"""Bait and Switch (Level 3) — Survivor Event.
选择一项：
- 躲避。若成功且该敌人为非[[精英]]，躲避该敌人并将其移动到一个连接地点。
- 躲避。只能对连接地点的一名非[[精英]]敌人使用。若成功，躲避该敌人并
  与其交换地点。

简化说明（与 lv0 相同的检定分工）：
- 躲避检定由会话层发起；成功后调用 resolve() 完成结算。
- 模式1（默认）：躲避交战/所在地点敌人并移动到连接地点（destination 可
  指定，默认第一个连接地点）。
- 模式2（switch=True）：目标必须在连接地点；躲避之，调查员移动到该敌人
  所在地点，敌人移动到调查员原地点（交换）。
"""

from backend.cards.base import CardImplementation
from backend.scenarios.official_core import is_elite_enemy


class BaitAndSwitchLv3(CardImplementation):
    card_id = "bait_and_switch_lv3"

    @staticmethod
    def resolve(game_state, investigator_id: str, enemy_instance_id: str,
                destination: str | None = None, switch: bool = False) -> bool:
        inv = game_state.get_investigator(investigator_id)
        enemy = game_state.get_card_instance(enemy_instance_id)
        if inv is None or enemy is None:
            return False
        enemy_data = game_state.get_card_data(enemy.card_id)
        if enemy_data is not None and is_elite_enemy(enemy_data):
            return False

        current_loc = game_state.get_location(inv.location_id)
        if current_loc is None:
            return False
        connections = list(getattr(current_loc, "connections", []) or [])

        if switch:
            # 模式2：目标须在一个连接地点（未交战）
            enemy_loc = None
            for loc in game_state.locations.values():
                if enemy_instance_id in loc.enemies:
                    enemy_loc = loc
                    break
            if enemy_loc is None or enemy_loc.location_id not in connections:
                return False
            # 躲避：横置（未交战，无需脱离）
            enemy.exhausted = True
            # 交换地点
            enemy_loc.enemies.remove(enemy_instance_id)
            current_loc.enemies.append(enemy_instance_id)
            enemy.attached_to = current_loc.location_id
            inv.location_id = enemy_loc.location_id
            return True

        # 模式1：躲避并移动到连接地点
        enemy.exhausted = True
        if enemy_instance_id in inv.threat_area:
            inv.threat_area.remove(enemy_instance_id)
        target = destination or (connections[0] if connections else None)
        if target is None or target not in game_state.locations:
            return False
        if enemy_instance_id in current_loc.enemies:
            current_loc.enemies.remove(enemy_instance_id)
        game_state.locations[target].enemies.append(enemy_instance_id)
        enemy.attached_to = target
        return True
