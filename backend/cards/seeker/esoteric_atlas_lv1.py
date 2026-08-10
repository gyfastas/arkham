"""Esoteric Atlas (Level 1) — Seeker Asset. (05232)
使用(4秘密)。[行动]花费1秘密并消耗绝密地图集：选择1个与你所在地点之间
连接次数恰好为2的已揭示地点。移动到该地点。

简化说明：
- 目标地点由 activate(target_location_id=...) 指定；缺省自动选择第一个
  最短路径恰好为2的已揭示地点（官方为玩家自选）；
- "连接次数恰好为2"按地点连接图的最短距离计算（中间地点无需已揭示，
  仅目的地必须已揭示）；
- 移动不携带交战敌人（引擎 _move 同款简化）；
- 数据 uses 键兼容双 s 写法（"secretss"），见 seeker/_uses.py。
"""

from collections import deque

from backend.cards.base import CardImplementation
from backend.cards.seeker._uses import uses_spend


class EsotericAtlas(CardImplementation):
    card_id = "esoteric_atlas_lv1"
    activations = [{
        "id": "jump",
        "label": "[行动]花1秘密并消耗：移动到恰好隔2个连接的已揭示地点",
        "method": "activate",
        "actions": 1,
    }]

    def activate(self, game_state, investigator_id: str,
                 target_location_id: str | None = None) -> bool:
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None or inst.exhausted:
            return False

        candidates = self._locations_two_away(game_state, inv.location_id)
        if target_location_id is not None:
            if target_location_id not in candidates:
                return False
            destination = target_location_id
        elif candidates:
            destination = candidates[0]
        else:
            return False

        if not uses_spend(inst, "secrets"):
            return False
        inst.exhausted = True
        inv.location_id = destination
        game_state.log_effect(
            f"🗺️ 绝密地图集：花费1秘密，移动到【{self._loc_name(game_state, destination)}】"
        )
        return True

    @staticmethod
    def _locations_two_away(game_state, start_location_id: str) -> list[str]:
        """BFS 求最短距离恰好为2的已揭示地点（保持发现顺序）。"""
        if start_location_id not in game_state.locations:
            return []
        dist = {start_location_id: 0}
        queue = deque([start_location_id])
        while queue:
            cur = queue.popleft()
            if dist[cur] >= 2:
                continue
            loc = game_state.get_location(cur)
            for nxt in (loc.connections if loc else []) or []:
                if nxt not in dist and nxt in game_state.locations:
                    dist[nxt] = dist[cur] + 1
                    queue.append(nxt)
        return [
            loc_id for loc_id, d in dist.items()
            if d == 2 and game_state.get_location(loc_id).revealed
        ]

    @staticmethod
    def _loc_name(game_state, location_id: str) -> str:
        loc = game_state.get_location(location_id)
        if loc is not None and loc.card_data is not None:
            return loc.card_data.name_cn or loc.card_data.name
        return location_id
