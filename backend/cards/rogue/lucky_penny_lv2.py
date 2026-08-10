""""Lucky" Penny (Level 2) — Rogue Asset. (07224)
卓绝。
强制 - 当你在正在进行的技能检定中揭示[bless]或[curse]标记时：掷1枚硬币。
正面，将该标记视为[bless]；反面，视为[curse]。若你因此将[bless]视为
[curse]，抽1张牌。

简化说明：
- 掷硬币为真随机（self._rng，测试可 seed/替换以确定性覆盖两面）。
- 视为[bless]/[curse]即修正变为+2/-2（改写本次检定的标记与修正，
  同 grotesque_statue 通道）；官方[bless]/[curse]的"再揭示1枚"连锁
  不由本卡触发（引擎单标记结算，列为简化）。
"""

import random

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import ChaosTokenType, GameEvent, TimingPriority


class LuckyPenny(CardImplementation):
    card_id = "lucky_penny_lv2"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._rng = random.Random()

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.FORCED)
    def flip_coin(self, ctx):
        if ctx.chaos_token not in (ChaosTokenType.BLESS, ChaosTokenType.CURSE):
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return

        original = ctx.chaos_token
        heads = self._rng.random() < 0.5
        treated = ChaosTokenType.BLESS if heads else ChaosTokenType.CURSE
        ctx.chaos_token = treated
        new_value = 2 if treated == ChaosTokenType.BLESS else -2
        ctx.modify_amount(new_value - (ctx.amount or 0), "lucky_penny_flip")
        ctx.extra["lucky_penny_treated_as"] = treated.value

        if original == ChaosTokenType.BLESS and treated == ChaosTokenType.CURSE:
            if inv.deck:
                inv.hand.append(inv.deck.pop(0))
                ctx.extra["lucky_penny_draw"] = True
            ctx.game_state.log_effect(
                "🪙 幸运硬币：反面，[bless]视为[curse]，抽1张牌")
        else:
            ctx.game_state.log_effect(
                f"🪙 幸运硬币：{'正面' if heads else '反面'}，视为[{treated.value}]")
