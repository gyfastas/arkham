"""Guidance (Level 0) — Seeker Event.
选择你所在地点1位本回合尚未执行回合的其他调查员。
该调查员在其本回合中可执行额外1个行动。

简化说明：
- 目标选择简化：默认你所在地点第一位本回合尚未行动的其他调查员，
  可用 ctx.extra["target_investigator"] 指定；
- "本回合尚未执行回合"依据引擎维护的 has_taken_turn 判定；
- 额外行动在该调查员回合开始时发放（INVESTIGATOR_TURN_BEGINS，
  在引擎发放3行动之后，与 Leo De Luca 同模式）；
- 若打出时无符合条件的目标，效果不生效（事件仍被打出）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class Guidance(CardImplementation):
    card_id = "guidance_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._grant: str | None = None

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def choose_target(self, ctx):
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return

        target_id = ctx.extra.get("target_investigator")
        if target_id is None:
            target_id = self._first_eligible(ctx, inv)
        target = ctx.game_state.get_investigator(target_id) if target_id else None
        if target is None or target.location_id != inv.location_id \
                or target.investigator_id == inv.investigator_id \
                or target.has_taken_turn:
            ctx.game_state.log_effect("🤝 指导：没有符合条件的目标调查员")
            return

        self._grant = target.investigator_id
        ctx.extra["guidance_target"] = target.investigator_id
        ctx.game_state.log_effect(
            f"🤝 指导：【{target.card_data.name_cn or target.card_data.name}】"
            "本回合可执行额外1个行动"
        )

    @staticmethod
    def _first_eligible(ctx, inv) -> str | None:
        for other in ctx.game_state.investigators.values():
            if other.investigator_id == inv.investigator_id:
                continue
            if other.location_id != inv.location_id:
                continue
            if other.has_taken_turn:
                continue
            return other.investigator_id
        return None

    @on_event(GameEvent.INVESTIGATOR_TURN_BEGINS, priority=TimingPriority.WHEN)
    def grant_extra_action(self, ctx):
        """目标回合开始时（在引擎发放3行动之后）：+1行动。"""
        if self._grant is None or ctx.investigator_id != self._grant:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is not None:
            inv.actions_remaining += 1
        self._grant = None

    @on_event(GameEvent.ROUND_ENDS, priority=TimingPriority.AFTER)
    def expire(self, ctx):
        """目标本轮始终未行动（如下轮才轮到）：授权过期。"""
        self._grant = None
