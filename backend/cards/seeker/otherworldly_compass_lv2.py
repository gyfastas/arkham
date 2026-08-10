"""Otherworldly Compass (Level 2) — Seeker Asset, Hand slot. (04194)
[行动]消耗异界罗盘：调查。这次调查中，你所在地点隐藏值-X。X为与你所在
地点相互连接、且已翻开的地点数。

简化说明：
- 检定由卡牌自身回放（CardSelfTest，无投入窗口；完整投入流程需会话层接线），
  与 in_the_know 同模式；
- X 在激活时按当前地点连接关系计算，难度 = max(0, 隐蔽值-X)；
- 成功发现你所在地点的1个线索并发 CLUE_DISCOVERED（与引擎调查行动一致）。
"""

from backend.cards.seeker._selftest import CardSelfTest
from backend.models.enums import GameEvent, Skill


class OtherworldlyCompass(CardSelfTest):
    card_id = "otherworldly_compass_lv2"
    activations = [{
        "id": "investigate",
        "label": "[行动]消耗：调查（隐蔽值-X，X=已揭示连接地点数）",
        "method": "activate",
        "actions": 1,
    }]

    def activate(self, game_state, investigator_id: str) -> bool:
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None or inst.exhausted:
            return False
        location = game_state.get_location(inv.location_id)
        if location is None:
            return False

        revealed_connections = sum(
            1 for cid in (location.connections or [])
            if (loc := game_state.get_location(cid)) is not None and loc.revealed
        )
        difficulty = max(0, location.shroud - revealed_connections)

        inst.exhausted = True
        result = self.run_self_test(
            game_state, investigator_id, Skill.INTELLECT, difficulty,
            source=self.instance_id,
        )
        if result is None:
            return False
        success, _margin = result
        if not success:
            game_state.log_effect("🧭 异界罗盘：调查失败")
            return True
        if location.clues > 0:
            location.clues -= 1
            inv.clues += 1
            self._emit_clue_discovered(game_state, investigator_id,
                                       location.location_id)
            game_state.log_effect(
                f"🧭 异界罗盘：调查成功（隐蔽值-{revealed_connections}），发现1个线索"
            )
        else:
            game_state.log_effect("🧭 异界罗盘：调查成功，但地点没有线索")
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
