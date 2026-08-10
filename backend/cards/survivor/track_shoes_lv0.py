"""Track Shoes (Level 0) — Survivor Asset (Footwear). (05036)
每位调查员限制1 [[鞋子]]。
你获得+1 [agility]。
[reaction] 在你移动后，新到地点的敌人与你交战之前，消耗钉鞋：检定
[agility](3)。如果你成功，移动到一个连接地点。

简化说明：
- +1 敏捷为常驻加值（SKILL_VALUE_DETERMINED 修正，在场即生效，无需准备）。
- 反应挂 ACTION_PERFORMED(MOVE)（引擎无"敌人交战前"窗口，移动后敌军的
  交战由会话/敌军阶段处理，本效果先于其触发即可）；自动消耗并检定敏捷(3)，
  成功则自动移动到第一个连接地点（官方为玩家自选目的地）。
- "每位调查员限1鞋子"为装备限制，由会话/构筑层约束。
- 检定经 CardSelfTest 回放（无投入窗口；混沌袋由 registry 入场激活时注入）。
"""

from backend.cards.base import on_event
from backend.cards.seeker._selftest import CardSelfTest
from backend.models.enums import Action, GameEvent, Skill, TimingPriority


class TrackShoes(CardSelfTest):
    card_id = "track_shoes_lv0"

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def agility_bonus(self, ctx):
        """常驻：+1 敏捷。"""
        if ctx.skill_type != Skill.AGILITY:
            return
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None or inst.owner_id != ctx.investigator_id:
            return
        ctx.modify_amount(1, "track_shoes_agility")

    @on_event(GameEvent.ACTION_PERFORMED, priority=TimingPriority.REACTION)
    def after_move(self, ctx):
        """你移动后：消耗钉鞋，检定敏捷(3)，成功则移动到一个连接地点。"""
        if ctx.action != Action.MOVE:
            return
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None or inst.exhausted or inst.owner_id != ctx.investigator_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return

        inst.exhausted = True
        result = self.run_self_test(
            ctx.game_state, inv.investigator_id, Skill.AGILITY, 3,
            source=self.instance_id,
        )
        if result is None:
            return
        success, _margin = result
        ctx.extra["track_shoes_success"] = success
        if not success:
            ctx.game_state.log_effect("👟 钉鞋：敏捷检定失败")
            return

        loc = ctx.game_state.get_location(inv.location_id)
        connections = (getattr(loc, "connections", None) or []) if loc else []
        destination = next(
            (c for c in connections if c in ctx.game_state.locations), None)
        if destination is None:
            return
        inv.location_id = destination
        ctx.extra["track_shoes_moved_to"] = destination
        ctx.game_state.log_effect("👟 钉鞋：检定成功，移动到连接地点")
