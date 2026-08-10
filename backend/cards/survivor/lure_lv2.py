"""Lure (Level 2) — Survivor Event. (02612 批次)
Attach to your location or to a connecting location.
During the enemy phase, each enemy that moves does so along the shortest
path toward the attached location, instead of to where it would normally
move.
Forced - While attached, at the end of the round: Discard Lure.

简化说明：
- 附加关系登记在 scenario.vars["lure_locations"]（同 hiding_spot /
  barricade 的 vars 标记模式）；目标地点默认为打出者所在地点，可经
  ctx.extra["location_id"] 指定（官方可叠加连接地点，需选择 UI）。
- 强制弃牌挂 ROUND_ENDS：移除标记（事件实例同轮被引擎清理，时序一致）。
- 引擎的敌军移动（phase_enemy._hunter_first_step）无"改道"挂钩：敌人
  改向标记地点的移动未实现（引擎缺口，见报告；vars 标记已就绪待接入）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class Lure(CardImplementation):
    card_id = "lure_lv2"

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def attach_to_location(self, ctx):
        """打出时：叠加到目标地点（默认你所在地点，可选连接地点）。"""
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        loc_id = ctx.extra.get("location_id") or inv.location_id
        loc = ctx.game_state.get_location(loc_id)
        if loc is None:
            return
        # 目标须为你所在地点或其连接地点
        current = ctx.game_state.get_location(inv.location_id)
        if loc_id != inv.location_id and (
                current is None or loc_id not in current.connections):
            return
        lured = ctx.game_state.scenario.vars.setdefault("lure_locations", [])
        if loc_id not in lured:
            lured.append(loc_id)
        ctx.extra["lure_location"] = loc_id
        ctx.game_state.log_effect(
            f"🎣 诱饵：叠加到【{ctx.game_state.card_name(loc_id)}】，"
            "敌军阶段中移动的敌人改向该地点")

    @on_event(GameEvent.ROUND_ENDS, priority=TimingPriority.AFTER)
    def forced_discard(self, ctx):
        """强制 - 回合结束时：丢弃诱饵（清除附加标记）。"""
        lured = ctx.game_state.scenario.vars.get("lure_locations")
        if not lured:
            return
        ctx.game_state.scenario.vars["lure_locations"] = []
        ctx.game_state.log_effect("🎣 诱饵：回合结束，诱饵被丢弃")
