"""Fingerprint Kit (Level 0) — Seeker Asset, Hand slot. (05024)
使用(3补给)。[行动]消耗指纹采集工具并花费1补给：调查。你这次调查+1智力。
如果你成功，你额外发现所在地点的1个线索。

简化说明：
- 检定由卡牌自身回放（CardSelfTest，无投入窗口；完整投入流程需会话层接线）；
- 调查目标为你所在地点（官方卡面即"你所在地点"的常规调查）；
- 成功时基础1线索+额外1线索（上限为地点剩余线索数），合并发一次
  CLUE_DISCOVERED（amount=实际发现数）。
"""

from backend.cards.base import on_event
from backend.cards.seeker._selftest import CardSelfTest
from backend.cards.seeker._uses import uses_spend
from backend.models.enums import GameEvent, Skill, TimingPriority


class FingerprintKit(CardSelfTest):
    card_id = "fingerprint_kit_lv0"
    activations = [{
        "id": "investigate",
        "label": "[行动]消耗+1补给：调查（+1智力，成功多发现1线索）",
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

        if not uses_spend(inst, "supplies"):
            return False
        inst.exhausted = True

        result = self.run_self_test(
            game_state, investigator_id, Skill.INTELLECT, location.shroud,
            source=self.instance_id,
        )
        if result is None:
            return False
        success, _margin = result
        if not success:
            game_state.log_effect("🔍 指纹采集工具：调查失败")
            return True

        found = min(2, location.clues)
        if found > 0:
            location.clues -= found
            inv.clues += found
            self._emit_clue_discovered(game_state, investigator_id,
                                       location.location_id, found)
        game_state.log_effect(f"🔍 指纹采集工具：调查成功，发现{found}个线索")
        return True

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def intellect_bonus(self, ctx):
        """本次调查 +1 智力。"""
        if ctx.skill_type != Skill.INTELLECT or ctx.source != self.instance_id:
            return
        ctx.modify_amount(1, "fingerprint_kit_bonus")

    def _emit_clue_discovered(self, game_state, investigator_id: str,
                              location_id: str, amount: int) -> None:
        bus = getattr(self, "_selftest_bus", None)
        if bus is None:
            return
        from backend.engine.event_bus import EventContext
        bus.emit(EventContext(
            game_state=game_state,
            event=GameEvent.CLUE_DISCOVERED,
            investigator_id=investigator_id,
            location_id=location_id,
            amount=amount,
            source=self.instance_id,
        ))
