"""In the Know (Level 1) — Seeker Asset.
使用(3秘密)。[行动]花费1秘密：调查。调查场上任意1个已揭示地点，
视为你身处该地点。

简化说明：
- 检定由卡牌自身回放（CardSelfTest，无投入窗口；完整投入流程需会话层接线）；
- 目标地点由 activate(target_location_id=...) 指定；缺省自动选择
  "第一个已揭示且有线索的其他地点"，均无则退回你所在地点；
- "视为身处该地点"仅结算隐蔽值难度与线索发现，不模拟地点其它效果。
"""

from backend.cards.seeker._selftest import CardSelfTest
from backend.models.enums import GameEvent, Skill


class InTheKnow(CardSelfTest):
    card_id = "in_the_know_lv1"
    activations = [{
        "id": "remote_investigate",
        "label": "[行动]花1秘密：调查任意已揭示地点",
        "method": "activate",
        "actions": 1,
    }]

    def activate(self, game_state, investigator_id: str,
                 target_location_id: str | None = None) -> bool:
        """[行动]花费1秘密：调查任意已揭示地点（默认自动选择）。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None or inst.uses.get("secrets", 0) <= 0:
            return False
        if getattr(self, "_selftest_bus", None) is None or \
                getattr(self, "_selftest_bag", None) is None:
            return False

        target = self._choose_target(game_state, inv, target_location_id)
        if target is None:
            return False

        inst.uses["secrets"] -= 1
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
                f"🗺️ 万事通：远程调查【{target.card_data.name_cn or target.card_data.name}】"
                "成功，发现1条线索"
            )
        elif success:
            game_state.log_effect("🗺️ 万事通：调查成功，但目标地点没有线索")
        else:
            game_state.log_effect("🗺️ 万事通：调查失败")
        return True

    @staticmethod
    def _choose_target(game_state, inv, target_location_id):
        if target_location_id is not None:
            return game_state.get_location(target_location_id)
        # 自动选择：优先第一个已揭示且有线索的其他地点
        for loc in game_state.locations.values():
            if loc.location_id == inv.location_id:
                continue
            if loc.revealed and loc.clues > 0:
                return loc
        # 兜底：你所在地点
        return game_state.get_location(inv.location_id)

    def _emit_clue_discovered(self, game_state, investigator_id: str,
                              location_id: str) -> None:
        from backend.engine.event_bus import EventContext
        ctx = EventContext(
            game_state=game_state,
            event=GameEvent.CLUE_DISCOVERED,
            investigator_id=investigator_id,
            location_id=location_id,
            amount=1,
            source=self.instance_id,
        )
        self._selftest_bus.emit(ctx)
