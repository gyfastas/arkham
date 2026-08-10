"""Archaic Glyphs (Guiding Stones, Level 3) — Seeker Asset.
已研究。使用(3充能)。[行动]花费1充能：调查。你每超出难度2点，
在你所在地点额外发现1条线索。

简化说明：
- "已研究"(Researched) 依赖战役日志状态，卡面层面不校验（视为已研究）；
- 检定由卡牌自身回放（CardSelfTest，无投入窗口；完整投入流程需会话层接线）。
  自检定路径不经 perform_action，因此也不会触发借机攻击。
"""

from backend.cards.seeker._selftest import CardSelfTest
from backend.models.enums import GameEvent, Skill


class ArchaicGlyphsGuidingStones(CardSelfTest):
    card_id = "archaic_glyphs_guiding_stones_lv3"
    activations = [{
        "id": "investigate",
        "label": "[行动]花1充能：调查；每超难度2点多发现1线索",
        "method": "activate",
        "actions": 1,
    }]

    def activate(self, game_state, investigator_id: str) -> bool:
        """[行动]花费1充能：调查；每超出难度2点额外发现1条线索。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None or inst.uses.get("charges", 0) <= 0:
            return False
        loc = game_state.get_location(inv.location_id)
        if loc is None:
            return False
        # 自检定需要事件总线与混沌袋（register/bind_chaos_bag 注入）
        if getattr(self, "_selftest_bus", None) is None or \
                getattr(self, "_selftest_bag", None) is None:
            return False

        inst.uses["charges"] -= 1
        result = self.run_self_test(
            game_state, investigator_id, Skill.INTELLECT, loc.shroud,
            source=self.instance_id,
        )
        if result is None:
            return False
        success, margin = result
        if success:
            total = 1 + max(0, margin // 2)
            discovered = min(total, loc.clues)
            loc.clues -= discovered
            inv.clues += discovered
            self._emit_clue_discovered(game_state, investigator_id,
                                       loc.location_id, discovered)
            game_state.log_effect(
                f"📜 古代雕文（指引之石）：调查成功（超难度{margin}点），"
                f"发现{discovered}条线索"
            )
        else:
            game_state.log_effect("📜 古代雕文（指引之石）：调查失败")
        return True

    def _emit_clue_discovered(self, game_state, investigator_id: str,
                              location_id: str, amount: int) -> None:
        from backend.engine.event_bus import EventContext
        ctx = EventContext(
            game_state=game_state,
            event=GameEvent.CLUE_DISCOVERED,
            investigator_id=investigator_id,
            location_id=location_id,
            amount=amount,
            source=self.instance_id,
        )
        self._selftest_bus.emit(ctx)
