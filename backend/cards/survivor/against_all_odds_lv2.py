"""Against All Odds (Level 2) — Survivor Event.
快速。在你执行一次难度高于你基础技能值的技能检定时打出。
为本次检定额外揭示X个混乱标记，选择其中1个结算并忽略其余。
X为检定难度与你基础技能值的差值。

简化说明：
- 从手牌自动打出：CHAOS_TOKEN_RESOLVED 时若难度>基础技能值且资源足够，
  自动支付2资源打出（官方为玩家选择时机）。
- "选择1个结算"简化为自动选择对调查员最有利的标记：数值标记按修正值比较，
  符号标记（含远古印记，场景相关数值引擎不可得）按0计，自动失败视为最差。
  选中标记经 ctx.amount 替换标记修正生效；原标记为自动失败而选中标记不是时，
  经 ctx.extra["cancel_auto_fail"] 通道取消自动失败（Eucatastrophe 同通道）。
- 符号标记的额外效果（骷髅等场景效果）不随选择重放（引擎缺口）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import (
    CHAOS_TOKEN_VALUES, ChaosTokenType, GameEvent, TimingPriority,
)


class AgainstAllOdds(CardImplementation):
    card_id = "against_all_odds_lv2"
    persistent_in_hand = True  # 在手牌中持续监听检定窗口

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._chaos_bag = None

    def bind_chaos_bag(self, chaos_bag) -> None:
        self._chaos_bag = chaos_bag

    @staticmethod
    def _score(token) -> float:
        """标记对调查员的有利度：自动失败最差，符号标记按0近似。"""
        if token == ChaosTokenType.AUTO_FAIL:
            return float("-inf")
        value = CHAOS_TOKEN_VALUES.get(token)
        return float(value) if value is not None else 0.0

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.WHEN)
    def reveal_additional_tokens(self, ctx):
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.card_id not in inv.hand:
            return
        base = inv.get_skill(ctx.skill_type)
        difficulty = ctx.difficulty or 0
        if difficulty <= base:
            return
        cd = ctx.game_state.get_card_data(self.card_id)
        cost = (getattr(cd, "cost", 2) or 2) if cd else 2
        if inv.resources < cost:
            return

        bag = self._chaos_bag or getattr(ctx.game_state, "chaos_bag", None)
        if bag is None or not getattr(bag, "tokens", None):
            return

        # 自动打出
        inv.resources -= cost
        inv.hand.remove(self.card_id)
        inv.discard.append(self.card_id)

        x_count = difficulty - base
        drawn = [bag.draw() for _ in range(x_count)]
        original = ctx.chaos_token
        candidates = [original] + drawn
        chosen = max(candidates, key=self._score)
        ctx.extra["against_all_odds_drawn"] = [
            getattr(t, "value", str(t)) for t in drawn]
        ctx.extra["against_all_odds_chosen"] = getattr(chosen, "value", str(chosen))

        if chosen is not original:
            if original == ChaosTokenType.AUTO_FAIL and chosen != ChaosTokenType.AUTO_FAIL:
                ctx.extra["cancel_auto_fail"] = True
            new_modifier = CHAOS_TOKEN_VALUES.get(chosen)
            if new_modifier is not None:
                ctx.amount = new_modifier
        ctx.game_state.log_effect(
            f"🎲 孤注一掷：额外揭示{x_count}个标记，"
            f"选择【{getattr(chosen, 'value', chosen)}】结算")
