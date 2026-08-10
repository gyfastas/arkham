"""Anatomical Diagrams (Level 0) — Seeker Event, Fast.
快速。可在任意调查员的回合中打出。仅有至少5点剩余理智时才能打出。
选择你所在地点的1个非精英敌人。直到当前行动调查员的回合结束，
该敌人-2战斗力、-2闪避值。

简化说明：
- 目标选择简化：默认你所在地点的第一个非精英敌人（交战优先），
  可用 ctx.extra["enemy_instance_id"] 指定；
- 减战斗力/闪避值以降低对应战斗/敏捷检定难度的方式生效
  （FIGHT/EVADE_ACTION_INITIATED 锁定检定目标，SKILL_TEST_BEGINS 降难度）；
- "剩余理智不足5点不能打出"简化为效果不生效（引擎出牌流程不支持前置条件回滚）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority
from backend.scenarios.official_core import is_elite_enemy


class AnatomicalDiagrams(CardImplementation):
    card_id = "anatomical_diagrams_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        # 被削弱的敌人实例（持续到当前调查员回合结束）
        self._target: str | None = None
        # 本次战斗/闪避检定的目标敌人（SKILL_TEST_BEGINS 无 enemy_id）
        self._test_enemy: str | None = None

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def choose_enemy(self, ctx):
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if inv.remaining_sanity < 5:
            ctx.extra["anatomical_diagrams_failed"] = "sanity"
            ctx.game_state.log_effect("🩺 解剖图谱：剩余理智不足5点，效果不生效")
            return
        enemy = self._choose_target(ctx, inv)
        if enemy is None:
            ctx.extra["anatomical_diagrams_failed"] = "no_target"
            return
        self._target = enemy.instance_id
        ctx.extra["anatomical_diagrams_target"] = enemy.instance_id
        ctx.game_state.log_effect(
            f"🩺 解剖图谱：【{ctx.game_state.card_name(enemy.card_id)}】"
            "本回合-2战斗力、-2闪避值"
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
            candidates += [e for e in loc.enemies if e not in candidates]
        for iid in candidates:
            inst = ctx.game_state.get_card_instance(iid)
            if inst is None:
                continue
            cd = ctx.game_state.get_card_data(inst.card_id)
            if cd is not None and not is_elite_enemy(cd):
                return inst
        return None

    @on_event(GameEvent.FIGHT_ACTION_INITIATED, priority=TimingPriority.WHEN)
    @on_event(GameEvent.EVADE_ACTION_INITIATED, priority=TimingPriority.WHEN)
    def track_test_target(self, ctx):
        self._test_enemy = ctx.enemy_id

    @on_event(GameEvent.SKILL_TEST_BEGINS, priority=TimingPriority.WHEN)
    def reduce_fight_and_evade(self, ctx):
        """对被削弱敌人的战斗/闪避检定：难度-2。"""
        if self._target is None or self._test_enemy != self._target:
            return
        if ctx.skill_type not in (Skill.COMBAT, Skill.AGILITY):
            return
        if ctx.difficulty is not None and ctx.difficulty > 0:
            ctx.difficulty = max(0, ctx.difficulty - 2)
            ctx.extra["anatomical_diagrams_reduced"] = True

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear_test_target(self, ctx):
        self._test_enemy = None

    @on_event(GameEvent.INVESTIGATOR_TURN_ENDS, priority=TimingPriority.AFTER)
    def expire(self, ctx):
        """"直到当前调查员回合结束"：任意回合结束即过期。"""
        self._target = None
        self._test_enemy = None
