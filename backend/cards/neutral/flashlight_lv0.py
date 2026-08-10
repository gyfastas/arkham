"""Flashlight (Level 0) — Neutral Asset, Hand slot.
使用(3补给)。[行动]花费1补给：调查。你所在地点的隐蔽值降低2，直到本次调查结束。

简化说明：
- activate() 花费1补给并武装；随后由会话层发起调查行动。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class Flashlight(CardImplementation):
    card_id = "flashlight_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._armed = False

    def activate(self, game_state, investigator_id: str) -> bool:
        """花费1补给：下一次调查隐蔽值-2。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None or inst.uses.get("supply", 0) <= 0:
            return False
        inst.uses["supply"] -= 1
        self._armed = True
        return True

    @on_event(GameEvent.SKILL_TEST_BEGINS, priority=TimingPriority.WHEN)
    def lower_shroud(self, ctx):
        """调查检定时：隐蔽值(难度)-2。"""
        if not self._armed or ctx.skill_type != Skill.INTELLECT:
            return
        if ctx.difficulty is not None and ctx.difficulty > 0:
            ctx.difficulty = max(0, ctx.difficulty - 2)
            ctx.extra["flashlight_lowered"] = True

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._armed = False
