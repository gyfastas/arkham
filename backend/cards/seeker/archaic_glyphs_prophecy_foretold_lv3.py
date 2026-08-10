"""Archaic Glyphs (Prophecy Foretold, Level 3) — Seeker Asset.
已研究。使用(3充能)。[行动]花费1充能：调查。如果成功，你可以自动躲避
1个与你交战的敌人。本行动不触发借机攻击。

简化说明：
- "已研究"(Researched) 依赖战役日志状态，卡面层面不校验（视为已研究）；
- 检定由卡牌自身回放（CardSelfTest，无投入窗口；完整投入流程需会话层接线）。
  自检定路径不经 perform_action，天然不触发借机攻击（与卡面一致）；
- "可以自动躲避1个交战敌人"简化为成功时自动躲避第一个交战敌人
  （官方为玩家选择目标/可选择不躲避）。
"""

from backend.cards.seeker._selftest import CardSelfTest
from backend.models.enums import GameEvent, Skill


class ArchaicGlyphsProphecyForetold(CardSelfTest):
    card_id = "archaic_glyphs_prophecy_foretold_lv3"
    activations = [{
        "id": "investigate",
        "label": "[行动]花1充能：调查；成功则自动躲避1个交战敌人",
        "method": "activate",
        "actions": 1,
    }]

    def activate(self, game_state, investigator_id: str) -> bool:
        """[行动]花费1充能：调查；成功则自动躲避1个交战敌人。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None or inst.uses.get("charges", 0) <= 0:
            return False
        loc = game_state.get_location(inv.location_id)
        if loc is None:
            return False
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
        success, _margin = result
        if success:
            if loc.clues > 0:
                loc.clues -= 1
                inv.clues += 1
                self._emit_clue_discovered(game_state, investigator_id,
                                           loc.location_id)
            evaded = self._auto_evade(game_state, inv, loc)
            game_state.log_effect(
                "📜 古代雕文（预言已现）：调查成功"
                + (f"，自动躲避【{game_state.card_name(evaded)}】" if evaded else "")
            )
        else:
            game_state.log_effect("📜 古代雕文（预言已现）：调查失败")
        return True

    def _auto_evade(self, game_state, inv, loc) -> str | None:
        """自动躲避第一个交战敌人：横置并移出威胁区。返回其 card_id。"""
        if not inv.threat_area:
            return None
        enemy_iid = inv.threat_area[0]
        enemy = game_state.get_card_instance(enemy_iid)
        if enemy is None:
            return None
        enemy.exhausted = True
        inv.threat_area.remove(enemy_iid)
        if enemy_iid not in loc.enemies:
            loc.enemies.append(enemy_iid)

        from backend.engine.event_bus import EventContext
        ctx = EventContext(
            game_state=game_state,
            event=GameEvent.ENEMY_EVADED,
            investigator_id=inv.investigator_id,
            enemy_id=enemy_iid,
        )
        self._selftest_bus.emit(ctx)
        return enemy.card_id

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
