"""Sure Gamble (Level 3) — Rogue Event.
快速。在你揭示一个混沌标记后打出。无视该混沌标记，改为揭示另一个混沌标记。

简化说明：
- 从手牌中自动触发（"快速"时机简化为自动）：揭示标记时若手牌中有老千手法，
  自动打出并重抽一次标记（redraw_provider 可注入混沌袋）。
"""

import random

from backend.cards.base import CardImplementation, on_event
from backend.models.chaos import STANDARD_BAG
from backend.models.enums import CHAOS_TOKEN_VALUES, GameEvent, TimingPriority


class SureGamble(CardImplementation):
    card_id = "sure_gamble_lv3"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self.redraw_provider = None
        self._rng = random.Random()

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.WHEN)
    def redraw_token(self, ctx):
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or "sure_gamble_lv3" not in inv.hand:
            return
        cd = ctx.game_state.get_card_data("sure_gamble_lv3")
        cost = getattr(cd, "cost", 2) or 2 if cd else 2
        if inv.resources < cost:
            return

        # 打出老千手法
        inv.resources -= cost
        inv.hand.remove("sure_gamble_lv3")
        inv.discard.append("sure_gamble_lv3")

        # 重抽一个标记
        if self.redraw_provider is not None:
            token = self.redraw_provider()
        else:
            token = self._rng.choice(list(STANDARD_BAG))
        ctx.chaos_token = token
        new_value = CHAOS_TOKEN_VALUES.get(token) or 0
        ctx.modify_amount(new_value - ctx.amount, "sure_gamble_redraw")
        ctx.extra["sure_gamble_redrawn"] = token
