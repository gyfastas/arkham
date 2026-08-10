"""Grotesque Statue (Level 4) — Mystic Asset, Hand slot. (01071)
使用(4充能)。如果诡秘石像上没有充能，弃置它。
[reaction] 在你将要揭示一个混沌标记时，花费1充能：改为揭示2个混沌标记。
选择其中1个结算，忽略另1个。

简化说明：
- 混沌袋通过 bind_chaos_bag() 注入（registry 在 activate_card 时已接线，
  测试可手动绑定）；未绑定时退化为独立随机标准袋。
- 二选一无选择 UI：自动结算对玩家较有利的标记（数值修正高者；
  [auto_fail] 视为最差；场景相关的符号标记按0估值）。
"""

import random

from backend.cards.base import CardImplementation, on_event
from backend.engine.slots import vacate_asset_slots
from backend.models.chaos import STANDARD_BAG
from backend.models.enums import CHAOS_TOKEN_VALUES, ChaosTokenType, GameEvent, TimingPriority


def _token_value(token) -> int:
    """对玩家有利程度的估值：auto_fail 最差，特殊符号按0，数值按面值。"""
    if token == ChaosTokenType.AUTO_FAIL:
        return -999
    return CHAOS_TOKEN_VALUES.get(token) or 0


class GrotesqueStatue(CardImplementation):
    card_id = "grotesque_statue_lv4"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._armed = False
        self._chaos_bag = None
        self._rng = random.Random()

    def bind_chaos_bag(self, chaos_bag) -> None:
        """注入游戏混沌袋（registry.activate_card 自动调用）。"""
        self._chaos_bag = chaos_bag

    def use(self, game_state, investigator_id: str) -> bool:
        """花费1充能：取消即将揭示的标记，改为揭示2枚选1枚。"""
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

        # 揭示2枚，取对玩家较有利者（简化：无二选一 UI）
        if self._chaos_bag is not None:
            drawn = [self._chaos_bag.draw(), self._chaos_bag.draw()]
        else:
            drawn = [self._rng.choice(list(STANDARD_BAG)),
                     self._rng.choice(list(STANDARD_BAG))]
        token = max(drawn, key=_token_value)
        ctx.extra["grotesque_statue_drawn"] = [t.value for t in drawn]
        ctx.extra["grotesque_statue_redrawn"] = token

        ctx.chaos_token = token
        new_value = CHAOS_TOKEN_VALUES.get(token) or 0
        ctx.modify_amount(new_value - ctx.amount, "grotesque_statue_redraw")
        if token == ChaosTokenType.AUTO_FAIL:
            ctx.extra["force_auto_fail"] = True

        self._discard_if_empty(ctx.game_state, inv)

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._armed = False
        # 无充能时弃置（覆盖 use() 后未触发重抽等情况）
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is not None and self.instance_id in inv.play_area:
            self._discard_if_empty(ctx.game_state, inv)

    def _discard_if_empty(self, game_state, inv) -> None:
        """没有充能时：弃置诡秘石像。"""
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None or inst.uses.get("charges", 0) > 0:
            return
        vacate_asset_slots(game_state, self.instance_id)
        if self.instance_id in inv.play_area:
            inv.play_area.remove(self.instance_id)
        inv.discard.append(self.card_id)
        game_state.cards_in_play.pop(self.instance_id, None)
