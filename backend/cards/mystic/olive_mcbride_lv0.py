"""Olive McBride (Level 0) — Mystic Asset, Ally slot. (02029)
[reaction] 当你将揭示1个混沌标记时，横置奥莉芙·麦克布莱德：改为揭示3个
混沌标记。选择其中2个结算，忽略另1个。

简化说明：
- 反应无选择 UI：奥莉芙就绪时自动触发并横置。
- 三选二无选择 UI：自动忽略对玩家最不利的1个标记（[auto_fail]最差；
  场景相关符号标记按0估值），结算其余2个（修正值相加）。
- 引擎检定上下文只承载单个标记：ctx.chaos_token 记为结算中较优者，
  全部揭示结果存 ctx.extra["olive_mcbride_tokens"]（引擎缺口：单次检定
  多标记结算无原生通道）。
- 混沌袋经 bind_chaos_bag() 注入（registry.activate_card 自动接线）。
"""

import random

from backend.cards.base import CardImplementation, on_event
from backend.models.chaos import STANDARD_BAG
from backend.models.enums import (
    CHAOS_TOKEN_VALUES, ChaosTokenType, GameEvent, TimingPriority,
)


def _token_value(token) -> int:
    if token == ChaosTokenType.AUTO_FAIL:
        return -999
    return CHAOS_TOKEN_VALUES.get(token) or 0


class OliveMcBride(CardImplementation):
    card_id = "olive_mcbride_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._chaos_bag = None
        self._rng = random.Random()

    def bind_chaos_bag(self, chaos_bag) -> None:
        self._chaos_bag = chaos_bag

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.WHEN)
    def reveal_three_choose_two(self, ctx):
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None or inst.exhausted:
            return
        inst.exhausted = True

        # 已揭示1个，再补抽2个凑成3个
        drawn = [ctx.chaos_token]
        for _ in range(2):
            if self._chaos_bag is not None:
                drawn.append(self._chaos_bag.draw())
            else:
                drawn.append(self._rng.choice(list(STANDARD_BAG)))

        # 忽略最差的1个，结算其余2个
        kept = sorted(drawn, key=_token_value, reverse=True)[:2]
        total = sum(_token_value(t) for t in kept)
        ctx.extra["olive_mcbride_tokens"] = [t.value for t in drawn]
        ctx.extra["olive_mcbride_kept"] = [t.value for t in kept]

        ctx.chaos_token = kept[0]
        ctx.modify_amount(total - ctx.amount, "olive_mcbride")
        if ChaosTokenType.AUTO_FAIL in kept:
            ctx.extra["force_auto_fail"] = True
        else:
            ctx.extra["cancel_auto_fail"] = True
