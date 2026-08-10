"""False Covenant (Level 2) — Rogue Asset, Permanent. (07116)
永久。牌组限1张[[圣约]]。
[反应]当你所在地点的一位调查员在技能检定中揭示[curse]标记时，消耗
假圣约：取消该混沌标记，将其放回标记池，并揭示另1个标记。

简化说明：
- "放回标记池再揭示另1个"：引擎的 ChaosBag.draw() 为非破坏性抽取，
  被取消的[curse]天然留在袋中；新标记直接改写本次检定的标记与修正
  （同 grotesque_statue 的重抽通道）。
- 新揭示[curse]时本卡已消耗，不会连锁；新标记的场景符号效果按0估值。
- "永久"（开局入场）为牌组规则，引擎无通道（引擎缺口）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import (
    CHAOS_TOKEN_VALUES, ChaosTokenType, GameEvent, TimingPriority,
)


class FalseCovenant(CardImplementation):
    card_id = "false_covenant_lv2"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._chaos_bag = None

    def bind_chaos_bag(self, chaos_bag) -> None:
        """注入游戏混沌袋（registry.activate_card 自动调用）。"""
        self._chaos_bag = chaos_bag

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.WHEN)
    def cancel_curse(self, ctx):
        if ctx.chaos_token != ChaosTokenType.CURSE:
            return
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None or inst.exhausted:
            return
        owner = ctx.game_state.get_investigator(inst.owner_id)
        tester = ctx.game_state.get_investigator(ctx.investigator_id)
        if owner is None or tester is None:
            return
        if self.instance_id not in owner.play_area:
            return
        if tester.location_id != owner.location_id:
            return
        if self._chaos_bag is None:
            return

        inst.exhausted = True
        token = self._chaos_bag.draw()
        ctx.chaos_token = token
        new_value = CHAOS_TOKEN_VALUES.get(token) or 0
        ctx.modify_amount(new_value - (ctx.amount or 0), "false_covenant_redraw")
        if token == ChaosTokenType.AUTO_FAIL:
            ctx.extra["force_auto_fail"] = True
        ctx.extra["false_covenant_redrawn"] = token.value
        ctx.game_state.log_effect(
            f"📿 假圣约：取消[curse]标记，重抽为[{token.value}]")
