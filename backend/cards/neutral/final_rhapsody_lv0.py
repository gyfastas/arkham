"""Final Rhapsody — Neutral Treachery, Signature Weakness (Jim Culver).
显现：从混乱袋中抽取5个混乱标记。每抽出1个[skull]或[auto_fail]，
受到1点伤害和1点恐惧。

简化说明：
- 混沌袋通过 bind_chaos_bag() 注入（会话层/测试在抽到后绑定）；
  抽取为非破坏性（标记不放回也不移除，仅展示）。未绑定时效果不触发。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import ChaosTokenType, GameEvent, TimingPriority


class FinalRhapsody(CardImplementation):
    card_id = "final_rhapsody_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._chaos_bag = None

    def bind_chaos_bag(self, chaos_bag) -> None:
        """注入混沌袋（Session/测试在抽到后调用）。"""
        self._chaos_bag = chaos_bag

    @on_event(GameEvent.CARD_DRAWN, priority=TimingPriority.WHEN)
    def revelation(self, ctx):
        if ctx.extra.get("card_id") != "final_rhapsody_lv0":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if "final_rhapsody_lv0" in inv.hand:
            inv.hand.remove("final_rhapsody_lv0")

        bad_tokens = 0
        drawn = []
        if self._chaos_bag is not None:
            for _ in range(5):
                token = self._chaos_bag.draw()
                drawn.append(token)
                if token in (ChaosTokenType.SKULL, ChaosTokenType.AUTO_FAIL):
                    bad_tokens += 1

        inv.damage += bad_tokens
        inv.horror += bad_tokens
        inv.discard.append("final_rhapsody_lv0")
        ctx.extra["final_rhapsody_drawn"] = drawn
        ctx.extra["final_rhapsody_bad_tokens"] = bad_tokens
