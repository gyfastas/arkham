"""Waylay (Level 0) — Survivor Event.
选择你所在地点一个消耗的非精英敌人并检定敏捷(X)，X为该敌人的躲避值。
如果你成功，击败该敌人。

简化说明：
- 目标选择简化：默认选你所在地点第一个消耗的非精英敌人（未交战的优先，
  其次与当地点调查员交战的），可经 ctx.extra["enemy_instance_id"] 指定。
- 检定由卡牌自身回放（CardSelfTest，无投入窗口；完整投入流程需会话层
  接线，同 expose_weakness_lv1 模式）。
- 击败结算为内联复制引擎流程（卡牌代码访问不到 DamageEngine；含胜利点
  数入 victory_display，同 aquinnah 模式）。
"""

from backend.cards.base import on_event
from backend.cards.seeker._selftest import CardSelfTest
from backend.models.enums import GameEvent, Skill, TimingPriority
from backend.scenarios.official_core import is_elite_enemy


class Waylay(CardSelfTest):
    card_id = "waylay_lv0"

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def test_agility_vs_evade(self, ctx):
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return

        enemy_iid = self._choose_target(ctx, inv)
        enemy = ctx.game_state.get_card_instance(enemy_iid) if enemy_iid else None
        if enemy is None:
            return
        enemy_data = ctx.game_state.get_card_data(enemy.card_id)
        if enemy_data is None:
            return

        result = self.run_self_test(
            ctx.game_state, inv.investigator_id, Skill.AGILITY,
            enemy_data.enemy_evade or 0, source=self.instance_id,
        )
        if result is None:
            return
        success, _margin = result
        ctx.extra["waylay_success"] = success
        ctx.extra["waylay_target"] = enemy_iid
        if success:
            self._defeat_enemy(ctx, enemy)
            ctx.game_state.log_effect(
                f"🪃 伏击：检定成功，【{ctx.game_state.card_name(enemy.card_id)}】被击败")
        else:
            ctx.game_state.log_effect("🪃 伏击：检定失败")

    def _choose_target(self, ctx, inv) -> str | None:
        """所在地点的消耗非精英敌人：显式指定 > 未交战 > 交战（当地点）。"""
        enemy_iid = ctx.extra.get("enemy_instance_id")
        if enemy_iid:
            enemy = ctx.game_state.get_card_instance(enemy_iid)
            if enemy is not None and enemy.exhausted:
                cd = ctx.game_state.get_card_data(enemy.card_id)
                if cd is not None and not is_elite_enemy(cd):
                    return enemy_iid
            return None

        loc = ctx.game_state.get_location(inv.location_id)
        if loc is not None:
            for iid in loc.enemies:
                if self._is_exhausted_non_elite(ctx, iid):
                    return iid
        for other in ctx.game_state.investigators.values():
            if other.location_id != inv.location_id:
                continue
            for iid in other.threat_area:
                if self._is_exhausted_non_elite(ctx, iid):
                    return iid
        return None

    @staticmethod
    def _is_exhausted_non_elite(ctx, enemy_iid) -> bool:
        enemy = ctx.game_state.get_card_instance(enemy_iid)
        if enemy is None or not enemy.exhausted:
            return False
        cd = ctx.game_state.get_card_data(enemy.card_id)
        return cd is not None and not is_elite_enemy(cd)

    @staticmethod
    def _defeat_enemy(ctx, enemy) -> None:
        """击败敌人（内联复制引擎流程，不发 ENEMY_DEFEATED 事件）。"""
        enemy_data = ctx.game_state.get_card_data(enemy.card_id)
        if enemy_data is not None and getattr(enemy_data, "victory", 0):
            ctx.game_state.scenario.victory_display.append(enemy.card_id)
        ctx.game_state.cards_in_play.pop(enemy.instance_id, None)
        for other in ctx.game_state.investigators.values():
            if enemy.instance_id in other.threat_area:
                other.threat_area.remove(enemy.instance_id)
        for loc in ctx.game_state.locations.values():
            if enemy.instance_id in loc.enemies:
                loc.enemies.remove(enemy.instance_id)
        ctx.game_state.scenario.encounter_discard.append(enemy.card_id)
