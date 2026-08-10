"""Pocket Telescope (Level 0) — Seeker Asset, Hand slot. (08097)
[快速]消耗袖珍望远镜：查看一个连接的未揭示地点的已揭示面。
[行动]：调查。调查一个连接的已揭示地点，如同你在那里。

简化说明：
- "查看"无引擎概念：peek() 消耗并记录到 scenario.vars["peeked_locations"]
  （供会话层向持有者展示牌面），返回目标地点 id；目标缺省为第一个连接
  的未揭示地点；
- 远程调查经 CardSelfTest 回放（无投入窗口；完整投入流程需会话层接线），
  按目标地点隐藏值检定智力，成功从该地点发现1条线索并补发
  CLUE_DISCOVERED（location_id 为目标地点）；
- 两项能力共用一个 activate 不合适，故拆为 peek / investigate_remote 两个
  公开方法并分别声明 activations。
"""

from backend.cards.seeker._selftest import CardSelfTest
from backend.models.enums import GameEvent, Skill


class PocketTelescope(CardSelfTest):
    card_id = "pocket_telescope_lv0"
    activations = [
        {
            "id": "peek",
            "label": "[快速]消耗：查看连接未揭示地点的已揭示面",
            "method": "peek",
        },
        {
            "id": "remote_investigate",
            "label": "[行动]调查：调查连接的已揭示地点（视为在那里）",
            "method": "investigate_remote",
            "actions": 1,
        },
    ]

    def _instance(self, game_state):
        return game_state.get_card_instance(self.instance_id)

    def peek(self, game_state, investigator_id: str,
             location_id: str | None = None) -> str | None:
        """[快速]消耗：查看一个连接的未揭示地点。返回该地点 id。"""
        inv = game_state.get_investigator(investigator_id)
        inst = self._instance(game_state)
        if inv is None or inst is None or inst.exhausted:
            return None
        current = game_state.get_location(inv.location_id)
        if current is None:
            return None

        target = None
        if location_id is not None:
            cand = game_state.get_location(location_id)
            if (cand is not None and not cand.revealed
                    and location_id in (current.connections or [])):
                target = cand
        else:
            for conn_id in (current.connections or []):
                cand = game_state.get_location(conn_id)
                if cand is not None and not cand.revealed:
                    target = cand
                    break
        if target is None:
            return None

        inst.exhausted = True
        peeked = game_state.scenario.vars.setdefault("peeked_locations", {})
        peeked.setdefault(investigator_id, []).append(target.location_id)
        game_state.log_effect(
            f"🔭 袖珍望远镜：查看了"
            f"【{game_state.card_name(target.location_id)}】的已揭示面")
        return target.location_id

    def investigate_remote(self, game_state, investigator_id: str,
                           location_id: str | None = None) -> bool:
        """[行动]调查一个连接的已揭示地点，如同你在那里。"""
        inv = game_state.get_investigator(investigator_id)
        inst = self._instance(game_state)
        if inv is None or inst is None:
            return False
        current = game_state.get_location(inv.location_id)
        if current is None:
            return False

        target = None
        if location_id is not None:
            cand = game_state.get_location(location_id)
            if (cand is not None and cand.revealed
                    and location_id in (current.connections or [])):
                target = cand
        else:
            for conn_id in (current.connections or []):
                cand = game_state.get_location(conn_id)
                if cand is not None and cand.revealed:
                    target = cand
                    break
        if target is None:
            return False

        result = self.run_self_test(
            game_state, investigator_id, Skill.INTELLECT, target.shroud,
            source=self.instance_id,
        )
        if result is None:
            return False
        success, _margin = result
        if success and target.clues > 0:
            target.clues -= 1
            inv.clues += 1
            self._emit_clue_discovered(game_state, investigator_id,
                                       target.location_id)
            game_state.log_effect(
                f"🔭 袖珍望远镜：远程调查"
                f"【{game_state.card_name(target.location_id)}】成功，发现1条线索")
        elif success:
            game_state.log_effect("🔭 袖珍望远镜：调查成功，但目标地点没有线索")
        else:
            game_state.log_effect("🔭 袖珍望远镜：远程调查失败")
        return True

    def _emit_clue_discovered(self, game_state, investigator_id: str,
                              location_id: str) -> None:
        bus = getattr(self, "_selftest_bus", None)
        if bus is None:
            return
        from backend.engine.event_bus import EventContext
        bus.emit(EventContext(
            game_state=game_state,
            event=GameEvent.CLUE_DISCOVERED,
            investigator_id=investigator_id,
            location_id=location_id,
            amount=1,
            source=self.instance_id,
        ))
