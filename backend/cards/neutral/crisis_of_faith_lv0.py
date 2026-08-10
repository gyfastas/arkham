"""Crisis of Faith (Level 0) — Neutral Treachery, Weakness.
显现：混沌袋中每有1个[bless]标记，你必须将其替换为1个[curse]标记，
或受到1点恐惧。

简化说明：
- 混沌袋通过 bind_chaos_bag() 注入（同 rexs_curse_lv0 惯例）。未绑定时
  视为袋中无可操作标记，直接弃牌。
- 每个[bless]的抉择（替换 vs 受恐惧）自动选择替换（玩家本可逐个选择；
  替换通常优于受恐惧）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import ChaosTokenType, GameEvent, TimingPriority


class CrisisOfFaith(CardImplementation):
    card_id = "crisis_of_faith_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._chaos_bag = None

    def bind_chaos_bag(self, chaos_bag) -> None:
        self._chaos_bag = chaos_bag

    @on_event(GameEvent.CARD_DRAWN, priority=TimingPriority.WHEN)
    def revelation(self, ctx):
        if ctx.extra.get("card_id") != "crisis_of_faith_lv0":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if "crisis_of_faith_lv0" in inv.hand:
            inv.hand.remove("crisis_of_faith_lv0")

        replaced = 0
        if self._chaos_bag is not None:
            bless_count = self._chaos_bag.tokens.count(ChaosTokenType.BLESS)
            for _ in range(bless_count):
                if self._chaos_bag.remove(ChaosTokenType.BLESS):
                    self._chaos_bag.add_token(ChaosTokenType.CURSE)
                    replaced += 1

        if replaced:
            ctx.game_state.log_effect(
                f"💔 信仰危机：{replaced}个[bless]被替换为[curse]")
        ctx.extra["crisis_of_faith_replaced"] = replaced
        inv.discard.append("crisis_of_faith_lv0")
