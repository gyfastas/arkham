"""Barricade (Level 0) — Seeker Event.
附加到你所在地点。非精英敌人不能移动进入被附加地点。
强制 - 当一位调查员离开被附加地点时：弃掉屏障。

简化说明：
- 附加关系记录在 scenario.vars["barricaded_locations"]；
  敌人生成逻辑（official_core._spawn_enemy_from_encounter）已接入检查
  （官方卡面只禁止"移动进入"，生成拦截见 dev_logs 审计报告待办）。
- "调查员离开时弃掉"通过 MOVE_ACTION_INITIATED 拦截：事件实现实例在
  ROUND_ENDS 被清理，故仅覆盖打出本轮内的离开；跨轮持续监听需要引擎/场景
  侧钩子（已列入审计报告待主代理处理）。
- "非精英敌人不能移动进入"需要引擎敌人移动事件钩子（phase_enemy 猎手移动），
  当前引擎无此事件，已列入报告。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class Barricade(CardImplementation):
    card_id = "barricade_lv0"

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def attach_to_location(self, ctx):
        """打出时：附加到你所在地点。"""
        if ctx.extra.get("card_id") != "barricade_lv0":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        locations = ctx.game_state.scenario.vars.setdefault("barricaded_locations", [])
        if inv.location_id not in locations:
            locations.append(inv.location_id)
        ctx.extra["barricaded_location"] = inv.location_id
        ctx.game_state.log_effect("🚧 屏障：附加到当前地点，非精英敌人不能移动进入")

    @on_event(GameEvent.MOVE_ACTION_INITIATED, priority=TimingPriority.WHEN)
    def discard_when_investigator_leaves(self, ctx):
        """强制 - 调查员离开被附加地点时：弃掉屏障。

        MOVE_ACTION_INITIATED 在移动生效前发出，inv.location_id 仍是出发地。
        """
        locations = ctx.game_state.scenario.vars.get("barricaded_locations", [])
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or inv.location_id not in locations:
            return
        locations.remove(inv.location_id)
        ctx.extra["barricade_discarded"] = inv.location_id
        ctx.game_state.log_effect("🚧 屏障：调查员离开被附加地点，屏障弃掉")
