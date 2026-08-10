"""Safeguard (Level 2) — Guardian Asset. (06196)
[reaction]在另一位调查员的回合中，消耗安全护卫：该调查员的回合接下来的
时间里，其从你所在地点移动到连接地点时，你也可以移动到该地点。

简化说明：
- activate() 由会话层在另一位调查员回合中调用（消耗本卡并武装跟随）；
  跟随为自动触发（官方"可以"的简化，取最有利分支）。
- 跟随判定：MOVE_ACTION_INITIATED 在移动生效前发出，此时移动者仍在出发
  地点；若出发地点即装备者所在地点且目的地与装备者地点相连，装备者随之
  移动。该回合结束时解除武装。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class Safeguard(CardImplementation):
    card_id = "safeguard_lv2"
    activations = [{
        "id": "follow",
        "label": "消耗：本回合跟随另一位调查员移动",
        "method": "activate",
        "actions": 0,
    }]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._armed = False

    def activate(self, game_state, investigator_id: str) -> bool:
        """[reaction] 消耗安全护卫：本回合跟随从你地点离开的调查员。"""
        inv = game_state.get_investigator(investigator_id)
        inst = game_state.get_card_instance(self.instance_id)
        if inv is None or inst is None or self.instance_id not in inv.play_area:
            return False
        if inst.exhausted:
            return False
        inst.exhausted = True
        self._armed = True
        game_state.log_effect("🛡️ 安全护卫：消耗，本回合跟随同地点调查员移动")
        return True

    @on_event(GameEvent.MOVE_ACTION_INITIATED, priority=TimingPriority.AFTER)
    def follow(self, ctx):
        """另一位调查员从你所在地点移向连接地点时：跟随移动。"""
        if not self._armed:
            return
        holder = self._holder(ctx.game_state)
        mover = ctx.game_state.get_investigator(ctx.investigator_id)
        if holder is None or mover is None:
            return
        if mover.investigator_id == holder.investigator_id:
            return
        # 事件在移动生效前发出：mover.location_id 仍为出发地点
        if mover.location_id != holder.location_id:
            return
        destination = ctx.location_id
        holder_loc = ctx.game_state.get_location(holder.location_id)
        if destination is None or holder_loc is None:
            return
        if destination not in (holder_loc.connections or []):
            return
        holder.location_id = destination
        ctx.game_state.log_effect(
            f"🛡️ 安全护卫：跟随 {mover.investigator_id} 移动至 {destination}")

    @on_event(GameEvent.INVESTIGATOR_TURN_ENDS, priority=TimingPriority.AFTER)
    def disarm(self, ctx):
        self._armed = False

    def _holder(self, game_state):
        for inv in game_state.investigators.values():
            if self.instance_id in inv.play_area:
                return inv
        return None
