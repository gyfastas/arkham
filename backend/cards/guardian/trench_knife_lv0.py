"""Trench Knife (Level 0) — Guardian Asset, Hand slot. (03147)
你执行的交战行动不会引起趁乱攻击。
[行动]：攻击。本次攻击你+X战斗，X为与你交战的敌人数量。

简化/缺口说明：
- "交战行动不引起趁乱攻击"：ATTACK_OF_OPPORTUNITY 上下文不携带行动类型，
  且引擎只对 FIGHT/INVESTIGATE/EVADE/MOVE 发出行动发起事件（PLAY/ENGAGE/
  DRAW/RESOURCE 均无发起事件；PLAY_ACTION_INITIATED 有定义但未发射）。
  实现采用行动标记法：对有发起事件的行动设标记，趁乱攻击发生时若无标记
  则视为交战行动并取消。偏差：DRAW/RESOURCE/PLAY/ACTIVATE 等无发起事件的
  行动会被一并豁免（引擎缺口，见报告）。
- +X 战斗按攻击发起时与你交战的敌人数量计算（含被攻击的敌人）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class TrenchKnife(CardImplementation):
    card_id = "trench_knife_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._tracked_action = False  # 当前行动有发起事件（非交战）

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def combat_bonus(self, ctx):
        """攻击时 +X 战斗，X = 与你交战的敌人数量。"""
        if ctx.source != self.instance_id:
            return
        if ctx.skill_type != Skill.COMBAT:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        x = len(ctx.game_state.get_engaged_enemies(inv.investigator_id))
        if x > 0:
            ctx.modify_amount(x, "trench_knife_combat_bonus")

    @on_event(GameEvent.FIGHT_ACTION_INITIATED, priority=TimingPriority.WHEN)
    @on_event(GameEvent.INVESTIGATE_ACTION_INITIATED, priority=TimingPriority.WHEN)
    @on_event(GameEvent.EVADE_ACTION_INITIATED, priority=TimingPriority.WHEN)
    @on_event(GameEvent.MOVE_ACTION_INITIATED, priority=TimingPriority.WHEN)
    def mark_tracked_action(self, ctx):
        """记录"有发起事件"的行动（这些行动不是交战；PLAY 无发起事件）。"""
        self._tracked_action = True

    @on_event(GameEvent.ACTION_PERFORMED, priority=TimingPriority.AFTER)
    def clear_tracked_action(self, ctx):
        self._tracked_action = False

    @on_event(GameEvent.ATTACK_OF_OPPORTUNITY, priority=TimingPriority.WHEN)
    def cancel_engage_aoo(self, ctx):
        """交战行动（无发起事件的行动）不引起趁乱攻击。"""
        if self._tracked_action:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        ctx.cancel()
        ctx.game_state.log_effect("🔪 战壕刀：交战行动不引起趁乱攻击")
