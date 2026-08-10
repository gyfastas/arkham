"""Stunning Blow (Level 0) — Survivor Skill. (04112)
如果攻击中的这次技能检定成功，自动躲避受到攻击的敌人。

简化说明：
- 投入的技能卡实现仅在检定流程内临时激活，看不到 FIGHT_ACTION_INITIATED
  （引擎检定上下文不带动作类型/攻击目标，引擎缺口），故"攻击中"近似为
  战斗检定（同 survival_instinct 的简化口径）。
- "受到攻击的敌人"由自动选择近似：优先取检定者威胁区中第一个准备好的敌人，
  否则取所在地点第一个敌人（官方为目标敌人）。
- 躲避延迟到 SKILL_TEST_ENDS 执行：攻击伤害已在 ST.7 结算；若敌人已被击败
  离场则不再躲避。
- 自动躲避=横置+脱离交战并放置于当前地点，不发 ENEMY_EVADED 事件
  （与 cunning_distraction/stray_cat 等"自动躲避"实现一致，从简）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class StunningBlow(CardImplementation):
    card_id = "stunning_blow_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._pending: str | None = None

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.AFTER)
    def mark_pending(self, ctx):
        """战斗检定成功且投入了本卡：记录待躲避。"""
        if self.card_id not in (ctx.committed_cards or []):
            return
        if ctx.skill_type != Skill.COMBAT:
            return
        self._pending = ctx.investigator_id

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def evade_enemy(self, ctx):
        try:
            if self._pending != ctx.investigator_id or not ctx.success:
                return
            inv = ctx.game_state.get_investigator(ctx.investigator_id)
            if inv is None:
                return
            enemy_iid = self._choose_enemy(ctx, inv)
            if enemy_iid is None:
                return
            enemy = ctx.game_state.get_card_instance(enemy_iid)
            if enemy is None:
                return  # 敌人已被击败离场

            enemy.exhausted = True
            for other in ctx.game_state.investigators.values():
                if enemy_iid in other.threat_area:
                    other.threat_area.remove(enemy_iid)
            loc = ctx.game_state.get_location(inv.location_id)
            if loc is not None and enemy_iid not in loc.enemies:
                loc.enemies.append(enemy_iid)
            ctx.extra["stunning_blow_evaded"] = enemy_iid
            ctx.game_state.log_effect(
                f"💫 晕眩重击：自动躲避【{ctx.game_state.card_name(enemy.card_id)}】")
        finally:
            self._pending = None

    @staticmethod
    def _choose_enemy(ctx, inv) -> str | None:
        """受到攻击的敌人（近似）：交战且准备好的优先，其次所在地点敌人。"""
        for enemy_iid in inv.threat_area:
            enemy = ctx.game_state.get_card_instance(enemy_iid)
            if enemy is not None and not enemy.exhausted:
                return enemy_iid
        loc = ctx.game_state.get_location(inv.location_id)
        if loc is not None:
            for enemy_iid in loc.enemies:
                if ctx.game_state.get_card_instance(enemy_iid) is not None:
                    return enemy_iid
        return None
