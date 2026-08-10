"""Survival Instinct (Level 0) — Survivor Skill.
If this skill test is successful during an evasion attempt, the evading
investigator may immediately disengage from each other enemy engaged with
him or her, and may move to a connecting location.

简化说明：
- 投入的技能卡实现仅在检定流程（ST.2 起）内临时激活，无法看到
  EVADE_ACTION_INITIATED，因此不区分"躲避尝试"：任何投入了本卡且成功的
  敏捷检定都会触发（审计认可的简化）。
- 脱离与移动延迟到 SKILL_TEST_ENDS 执行：被躲避的敌人由引擎在 ST.7 移出
  威胁区并放置于原地点，此时威胁区剩余的即为"每个其他交战敌人"，
  且移动不会把被躲避的敌人错误带到新地点。
- 移动自动选择第一个连接地点（官方为"可以移动"，由玩家选择）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class SurvivalInstinct(CardImplementation):
    card_id = "survival_instinct_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._pending: str | None = None

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.AFTER)
    def mark_pending(self, ctx):
        if "survival_instinct_lv0" not in ctx.committed_cards:
            return
        if ctx.skill_type != Skill.AGILITY:
            return
        self._pending = ctx.investigator_id

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def disengage_and_move(self, ctx):
        try:
            if self._pending != ctx.investigator_id or not ctx.success:
                return
            inv = ctx.game_state.get_investigator(ctx.investigator_id)
            if inv is None:
                return
            loc = ctx.game_state.get_location(inv.location_id)
            if loc is None:
                return

            # 与每个其他交战敌人脱离（被躲避的敌人已由引擎移出威胁区）
            disengaged = []
            for enemy_iid in list(inv.threat_area):
                inv.threat_area.remove(enemy_iid)
                if enemy_iid not in loc.enemies:
                    loc.enemies.append(enemy_iid)
                disengaged.append(enemy_iid)
            ctx.extra["survival_instinct_disengaged"] = disengaged

            # 移动到一个连接地点（简化：自动选第一个）
            connections = getattr(loc, "connections", []) or []
            if connections and connections[0] in ctx.game_state.locations:
                inv.location_id = connections[0]
                ctx.extra["survival_instinct_moved_to"] = connections[0]
        finally:
            self._pending = None
