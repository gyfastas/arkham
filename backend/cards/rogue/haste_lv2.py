"""Haste (Level 2) — Rogue Asset. (06239)
每名调查员限1张。
[反应]在你连续执行两个相同类型的行动后，消耗迅捷：再次执行1个该类型的
行动（类型包括启动、交战、躲避、战斗、调查、移动、打出、资源、抽牌）。

简化说明：
- "再次执行1个该类型的行动"简化为 +1 行动次数（类型限制由会话层执行；
  引擎的 actions_remaining 不区分行动类型）。
- 行动类型经 ACTION_PERFORMED 跟踪；连续两个相同行动即触发并重置计数
  （本卡消耗后直到准备前不再触发）。
- 引擎对快速行动同样发射 ACTION_PERFORMED，快速行动也会计入连续计数
  （与官方"行动"定义略有差异，列为简化）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class Haste(CardImplementation):
    card_id = "haste_lv2"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._last_action = None
        self._streak = 0

    @on_event(GameEvent.ACTION_PERFORMED, priority=TimingPriority.AFTER)
    def track_actions(self, ctx):
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None or inst.owner_id != ctx.investigator_id:
            return
        inv = ctx.game_state.get_investigator(inst.owner_id)
        if inv is None or self.instance_id not in inv.play_area:
            return

        if ctx.action is not None and ctx.action == self._last_action:
            self._streak += 1
        else:
            self._last_action = ctx.action
            self._streak = 1

        if self._streak >= 2 and not inst.exhausted:
            inst.exhausted = True
            inv.actions_remaining += 1
            self._streak = 0
            ctx.extra["haste_extra_action"] = getattr(
                ctx.action, "name", str(ctx.action))
            ctx.game_state.log_effect("💨 迅捷：连续两个相同行动，+1行动")
