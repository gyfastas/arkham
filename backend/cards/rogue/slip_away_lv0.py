"""Slip Away (Level 0) — Rogue Event. (04232)
躲避。本次躲避尝试将你的[intellect]加入你的技能值。如果你成功且超过难度
至少2点，且被躲避的敌人非[[精英]]，该敌人在下一个补给阶段不进入准备状态。

简化说明：
- 打出后武装，由会话层发起躲避行动；目标敌人在 EVADE_ACTION_INITIATED
  捕获。
- "下一个补给阶段不准备"：引擎刷新流程先就绪再发 CARD_READIED，无法阻止；
  近似为 CARD_READIED 时重新横置一次（同 jacob_morrison 模式），下一个
  补给阶段之后敌人正常准备。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority
from backend.scenarios.official_core import is_elite_enemy


class SlipAway(CardImplementation):
    card_id = "slip_away_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._armed = False
        self._enemy_id: str | None = None
        self._no_ready: str | None = None

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def arm(self, ctx):
        if ctx.extra.get("card_id") == self.card_id:
            self._armed = True

    @on_event(GameEvent.EVADE_ACTION_INITIATED, priority=TimingPriority.WHEN)
    def capture_target(self, ctx):
        if self._armed:
            self._enemy_id = ctx.enemy_id

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def add_intellect(self, ctx):
        """本次躲避尝试将[intellect]加入技能值。"""
        if not self._armed or ctx.skill_type != Skill.AGILITY:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        intellect = inv.get_skill(Skill.INTELLECT)
        if intellect:
            ctx.modify_amount(intellect, "slip_away_intellect")

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.AFTER)
    def mark_no_ready(self, ctx):
        """成功2点以上且目标非精英：下个补给阶段不准备。"""
        if not self._armed or ctx.skill_type != Skill.AGILITY:
            return
        margin = (ctx.modified_skill or 0) - (ctx.difficulty or 0)
        if margin < 2 or self._enemy_id is None:
            return
        enemy = ctx.game_state.get_card_instance(self._enemy_id)
        if enemy is None:
            return
        ed = ctx.game_state.get_card_data(enemy.card_id)
        if ed is not None and is_elite_enemy(ed):
            return
        self._no_ready = self._enemy_id
        ctx.extra["slip_away_no_ready"] = self._enemy_id
        ctx.game_state.log_effect("💨 溜走：敌人下个补给阶段不准备")

    @on_event(GameEvent.CARD_READIED, priority=TimingPriority.AFTER)
    def suppress_ready(self, ctx):
        """被标记敌人在补给阶段被就绪后立即重新横置（仅一次）。"""
        if self._no_ready is None or ctx.target != self._no_ready:
            return
        enemy = ctx.game_state.get_card_instance(ctx.target)
        if enemy is not None:
            enemy.exhausted = True
            ctx.game_state.log_effect("💨 溜走：敌人在本补给阶段不准备")
        self._no_ready = None

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._armed = False
        self._enemy_id = None
