"""Grotesque Statue (Level 4) — Mystic Asset, Hand slot.
使用(4充能)。快速。在你揭示一个混沌标记时：花费1充能。取消该标记，改为揭示另一个混沌标记。

简化说明：
- 参考 Wendy Adams 的重抽模式：use() 武装后，下一次 CHAOS_TOKEN_RESOLVED
  用 redraw_provider（可注入 game.chaos_bag.draw；默认独立随机标准袋）替换修正值。
"""

import random

from backend.cards.base import CardImplementation, on_event
from backend.models.chaos import STANDARD_BAG
from backend.models.enums import CHAOS_TOKEN_VALUES, ChaosTokenType, GameEvent, TimingPriority


class GrotesqueStatue(CardImplementation):
    card_id = "grotesque_statue_lv4"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._armed = False
        self.redraw_provider = None
        self._rng = random.Random()

    def use(self, game_state, investigator_id: str) -> bool:
        """花费1充能：取消即将揭示的标记，改揭示另一个。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None or inst.uses.get("charges", 0) <= 0:
            return False
        inst.uses["charges"] -= 1
        self._armed = True
        return True

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.WHEN)
    def redraw_token(self, ctx):
        if not self._armed:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        self._armed = False
        if self.redraw_provider is not None:
            token = self.redraw_provider()
        else:
            token = self._rng.choice(list(STANDARD_BAG))
        ctx.chaos_token = token
        new_value = CHAOS_TOKEN_VALUES.get(token) or 0
        ctx.modify_amount(new_value - ctx.amount, "grotesque_statue_redraw")
        ctx.extra["grotesque_statue_redrawn"] = token

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._armed = False
