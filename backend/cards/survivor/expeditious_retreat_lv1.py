"""Expeditious Retreat (Level 1) — Survivor Skill.
每次技能检定最多投入1张。
只要在基础躲避行动中投入迅速撤退，其获得[敏捷][敏捷]和以下文本：
"若本次检定成功且超过难度至少2点，你可以自动躲避你所在地点的另一名敌人。"

简化说明：
- 投入的卡实现仅在检定流程内临时激活，无法区分"基础躲避行动"与其他
  敏捷检定（同 survival_instinct 的既有简化）：任何投入了本卡的敏捷检定
  均生效。
- "最多投入1张"为投入限制：引擎无投入校验钩子（引擎缺口）。
- 自动躲避延迟到 SKILL_TEST_ENDS（被躲避的首个敌人已由引擎结算）：
  优先选仍与你交战的敌人，其次你所在地点的未交战敌人；自动选择第一个
  （官方为玩家选择"另一名"），躲避=横置+脱离交战并留在地点，并补发
  ENEMY_EVADED 事件。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class ExpeditiousRetreat(CardImplementation):
    card_id = "expeditious_retreat_lv1"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._pending: str | None = None
        self._bus = None

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus

    @on_event(GameEvent.SKILL_TEST_COMMIT, priority=TimingPriority.WHEN)
    def bonus_icons(self, ctx):
        """基础躲避中投入：额外[敏捷][敏捷]（对敏捷检定+2）。"""
        if self.card_id not in ctx.committed_cards:
            return
        if ctx.skill_type != Skill.AGILITY:
            return
        ctx.modify_amount(2, "expeditious_retreat_icons")

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.AFTER)
    def mark_pending(self, ctx):
        if self.card_id not in ctx.committed_cards:
            return
        if ctx.skill_type != Skill.AGILITY:
            return
        margin = (ctx.modified_skill or 0) - (ctx.difficulty or 0)
        if margin >= 2:
            self._pending = ctx.investigator_id

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def evade_another(self, ctx):
        try:
            if self._pending != ctx.investigator_id or not ctx.success:
                return
            inv = ctx.game_state.get_investigator(ctx.investigator_id)
            if inv is None:
                return
            loc = ctx.game_state.get_location(inv.location_id)

            # 目标：优先仍交战的敌人，其次地点上的未交战敌人
            target_iid = inv.threat_area[0] if inv.threat_area else None
            if target_iid is None and loc is not None and loc.enemies:
                target_iid = loc.enemies[0]
            if target_iid is None:
                return
            enemy = ctx.game_state.get_card_instance(target_iid)
            if enemy is None:
                return

            enemy.exhausted = True
            if target_iid in inv.threat_area:
                inv.threat_area.remove(target_iid)
            if loc is not None and target_iid not in loc.enemies:
                loc.enemies.append(target_iid)
            ctx.extra["expeditious_retreat_evaded"] = target_iid
            ctx.game_state.log_effect(
                f"🏃 迅速撤退：自动躲避【{ctx.game_state.card_name(enemy.card_id)}】")

            if self._bus is not None:
                from backend.engine.event_bus import EventContext
                self._bus.emit(EventContext(
                    game_state=ctx.game_state,
                    event=GameEvent.ENEMY_EVADED,
                    investigator_id=ctx.investigator_id,
                    enemy_id=target_iid,
                ))
        finally:
            self._pending = None
