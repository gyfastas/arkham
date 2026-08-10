"""Dark Prophecy (Level 0) — Mystic Event. (04032)
快速。在你将要揭示一个混乱标记时打出。改为揭示5个混乱标记，而不是1个。
从这些标记中选择1个[skull]、[cultist]、[tablet]、[elder_thing]或[auto_fail]
标记来结算，忽略其余标记。（如果没有揭示上述标记，从这些标记中选择任意1个
来结算，忽略其余标记。）

简化说明：
- 从手牌中自动触发（同 a_test_of_will 惯例）：你的检定即将结算标记时，
  若手牌中有黑暗预言且资源足够，自动打出（付1资源）。
- 标记替换发生在 CHAOS_TOKEN_RESOLVED（引擎 ST.3 抽袋在事件前，与
  grotesque_statue 同一通道；被替换的原标记等效"从未揭示"）。
- 五选一无选择 UI：坏符号中自动避开[auto_fail]、取第一个其他坏符号
  （全为[auto_fail]时只能取[auto_fail]）；无坏符号时取数值最高者。
- 混沌袋经 bind_chaos_bag() 注入（registry.activate_card 自动接线）；
  未绑定时退化为独立随机标准袋。
"""

import random

from backend.cards.base import CardImplementation, on_event
from backend.models.chaos import STANDARD_BAG
from backend.models.enums import CHAOS_TOKEN_VALUES, ChaosTokenType, GameEvent, TimingPriority

_BAD_SYMBOLS = {
    ChaosTokenType.SKULL, ChaosTokenType.CULTIST,
    ChaosTokenType.TABLET, ChaosTokenType.ELDER_THING,
    ChaosTokenType.AUTO_FAIL,
}


class DarkProphecy(CardImplementation):
    card_id = "dark_prophecy_lv0"
    persistent_in_hand = True  # 在手牌中持续监听标记揭示窗口

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._armed = False
        self._spent = False
        self._chaos_bag = None
        self._rng = random.Random()

    def bind_chaos_bag(self, chaos_bag) -> None:
        """注入游戏混沌袋（registry.activate_card 自动调用）。"""
        self._chaos_bag = chaos_bag

    @on_event(GameEvent.CHAOS_TOKEN_REVEALED, priority=TimingPriority.WHEN)
    def play_when_revealing(self, ctx):
        """你将要揭示标记时：自动从手牌打出。"""
        if self._spent or self._armed:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.card_id not in inv.hand:
            return
        my_cd = ctx.game_state.get_card_data(self.card_id)
        cost = (getattr(my_cd, "cost", 1) or 1) if my_cd else 1
        if inv.resources < cost:
            return
        inv.resources -= cost
        inv.hand.remove(self.card_id)
        inv.discard.append(self.card_id)
        self._armed = True
        self._spent = True
        ctx.extra["dark_prophecy_played"] = True

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.WHEN)
    def replace_with_five(self, ctx):
        """改为揭示5个标记，按规则选择1个结算。"""
        if not self._armed:
            return
        self._armed = False

        if self._chaos_bag is not None:
            drawn = [self._chaos_bag.draw() for _ in range(5)]
        else:
            drawn = [self._rng.choice(list(STANDARD_BAG)) for _ in range(5)]
        ctx.extra["dark_prophecy_drawn"] = [t.value for t in drawn]

        chosen = self._choose(drawn)
        ctx.extra["dark_prophecy_chosen"] = chosen.value

        ctx.chaos_token = chosen
        new_value = CHAOS_TOKEN_VALUES.get(chosen) or 0
        ctx.modify_amount(new_value - ctx.amount, "dark_prophecy_replace")
        # 原标记可能是 auto_fail（ST.4 事件前已标记）；替换后按新标记结算
        if chosen == ChaosTokenType.AUTO_FAIL:
            ctx.extra["force_auto_fail"] = True
        else:
            ctx.extra["cancel_auto_fail"] = True
        ctx.game_state.log_effect(
            f"🔮 黑暗预言：揭示5标记，结算[{chosen.value}]")

    @staticmethod
    def _choose(drawn) -> ChaosTokenType:
        """按卡面规则选择：有坏符号必须选坏符号（自动避开auto_fail取第一个
        其他坏符号）；无坏符号任选（取数值最高者）。"""
        bad = [t for t in drawn if t in _BAD_SYMBOLS]
        if bad:
            non_auto_fail = [t for t in bad if t != ChaosTokenType.AUTO_FAIL]
            return (non_auto_fail or bad)[0]
        return max(drawn, key=lambda t: CHAOS_TOKEN_VALUES.get(t) or 0)
