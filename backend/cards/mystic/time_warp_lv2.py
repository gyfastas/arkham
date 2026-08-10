"""Time Warp (Level 2) — Mystic Event. (03311)
快速。你所在地点的一位调查员在其回合结算完毕一次行动之后，立即打出本卡。
<b>撤销</b>该行动（游戏返回到该行动执行之前的状态，但你仍视为打出了
时间曲折，且本卡的费用不会返还）。

简化说明：
- 引擎无游戏状态快照/回滚机制（引擎缺口），"撤销行动"简化为：向目标调查员
  返还1点行动数（撤销最常见的实质损失——行动点本身），不回滚伤害/线索/
  资源等状态变化。
- 目标默认当前回合的行动者（经 INVESTIGATOR_TURN_BEGINS 跟踪），须与你
  同地点；可用 ctx.extra["target_investigator_id"] 指定。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class TimeWarp(CardImplementation):
    card_id = "time_warp_lv2"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._turn_investigator: str | None = None

    @on_event(GameEvent.INVESTIGATOR_TURN_BEGINS, priority=TimingPriority.AFTER)
    def track_turn(self, ctx):
        self._turn_investigator = ctx.investigator_id

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def undo_action(self, ctx):
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return

        target_id = ctx.extra.get("target_investigator_id") \
            or self._turn_investigator or ctx.investigator_id
        target = ctx.game_state.get_investigator(target_id)
        if target is None or target.location_id != inv.location_id:
            return

        # 简化：返还1行动点（完整状态回滚需引擎快照支持）
        target.actions_remaining += 1
        ctx.extra["time_warp_undone_for"] = target_id
        ctx.game_state.log_effect(
            f"⏳ 时间曲折：撤销【{target.card_data.name_cn}】的行动，返还1行动点")
