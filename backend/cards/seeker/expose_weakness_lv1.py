"""Expose Weakness (Level 1) — Seeker Event, Fast.
快速。可在任意[快速]玩家窗口打出。
选择一个在你地点的敌人。检定智力(X)，X为该敌人的战斗力。
你每超出1点难度，本阶段内下一次对该敌人的攻击，其战斗力-1。

简化说明：
- 目标默认为你所在地点的第一个敌人（交战优先），可用 ctx.extra["enemy_instance_id"] 指定；
- 检定由卡牌自身回放（CardSelfTest，无投入窗口；完整投入流程需会话层接线）；
- 减战斗力在下一次对该敌人的战斗检定（FIGHT_ACTION_INITIATED 锁定目标后的
  SKILL_TEST_BEGINS）以降低难度的方式生效，阶段结束（调查/敌人）时过期。
"""

from backend.cards.base import on_event
from backend.cards.seeker._selftest import CardSelfTest
from backend.models.enums import GameEvent, Skill, TimingPriority


class ExposeWeakness(CardSelfTest):
    card_id = "expose_weakness_lv1"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        # {enemy_instance_id: 减战斗力点数}（本阶段下一次对其攻击生效）
        self._fight_reductions: dict[str, int] = {}
        # FIGHT_ACTION_INITIATED 锁定的攻击目标（SKILL_TEST_BEGINS 无 enemy_id）
        self._fight_target: str | None = None

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def test_intellect_vs_fight(self, ctx):
        if ctx.extra.get("card_id") != "expose_weakness_lv1":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return

        enemy = self._choose_target(ctx, inv)
        if enemy is None:
            return
        enemy_data = ctx.game_state.get_card_data(enemy.card_id)
        if enemy_data is None:
            return

        result = self.run_self_test(
            ctx.game_state, inv.investigator_id, Skill.INTELLECT,
            enemy_data.enemy_fight or 0, source=self.instance_id,
        )
        if result is None:
            return
        success, margin = result
        ctx.extra["expose_weakness_success"] = success
        if success and margin > 0:
            self._fight_reductions[enemy.instance_id] = margin
            ctx.extra["expose_weakness_reduction"] = margin
            ctx.game_state.log_effect(
                f"🎯 暴露弱点：检定超难度{margin}点，本阶段下一次对其攻击其战斗力-{margin}"
            )

    def _choose_target(self, ctx, inv):
        enemy_iid = ctx.extra.get("enemy_instance_id")
        if enemy_iid:
            enemy = ctx.game_state.get_card_instance(enemy_iid)
            if enemy is not None:
                return enemy
        candidates = list(inv.threat_area)
        loc = ctx.game_state.get_location(inv.location_id)
        if loc is not None:
            candidates += list(loc.enemies)
        for iid in candidates:
            inst = ctx.game_state.get_card_instance(iid)
            if inst is not None:
                return inst
        return None

    @on_event(GameEvent.FIGHT_ACTION_INITIATED, priority=TimingPriority.WHEN)
    def track_fight_target(self, ctx):
        self._fight_target = ctx.enemy_id

    @on_event(GameEvent.SKILL_TEST_BEGINS, priority=TimingPriority.WHEN)
    def reduce_fight_for_next_attack(self, ctx):
        """下一次对该敌人的攻击：战斗力按超出点数降低（以降低难度实现）。"""
        if ctx.skill_type != Skill.COMBAT:
            return
        target = self._fight_target
        if target is None or target not in self._fight_reductions:
            return
        reduction = self._fight_reductions.pop(target)
        ctx.difficulty = max(0, (ctx.difficulty or 0) - reduction)
        ctx.extra["expose_weakness_reduced"] = reduction

    @on_event(GameEvent.INVESTIGATION_PHASE_ENDS, priority=TimingPriority.AFTER)
    @on_event(GameEvent.ENEMY_PHASE_ENDS, priority=TimingPriority.AFTER)
    def expire_reductions(self, ctx):
        """"本阶段"结束：未用的减战斗力过期。"""
        self._fight_reductions.clear()
        self._fight_target = None
