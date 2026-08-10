"""All In (Level 5) — Rogue Skill. (04309)
每次技能检定最多投入1张。
如果本次检定成功，你每超过难度1点，抽取1张卡牌，最多可抽取5张。将本效果
中抽到的所有弱点洗回你的牌堆，而不进行结算。

简化说明：
- "每次检定最多投入1张"由会话层投入校验负责（引擎提交通道不限制）。
- 抽牌在 SKILL_TEST_SUCCESSFUL（ST.6，投入的卡尚未弃置）结算，与 Guts
  等"成功后抽牌"同窗口。
- 抽到的弱点不结算、直接洗回牌堆（random.shuffle 整堆——官方只洗回这些
  弱点，整堆重洗分布等价）。
"""

import random

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority
from backend.models.state import is_weakness_card

_MAX_DRAW = 5


class AllIn(CardImplementation):
    card_id = "all_in_lv5"

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.AFTER)
    def draw_per_margin(self, ctx):
        """成功：每超出难度1点抽1张（至多5），弱点洗回牌堆不结算。"""
        if self.card_id not in (ctx.committed_cards or []):
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        margin = (ctx.modified_skill or 0) - (ctx.difficulty or 0)
        draws = max(0, min(_MAX_DRAW, margin))
        if draws <= 0:
            return

        drawn: list[str] = []
        weaknesses: list[str] = []
        for _ in range(draws):
            if not inv.deck:
                break
            card_id = inv.deck.pop(0)
            if is_weakness_card(ctx.game_state.get_card_data(card_id)):
                weaknesses.append(card_id)
            else:
                inv.hand.append(card_id)
                drawn.append(card_id)
        if weaknesses:
            inv.deck.extend(weaknesses)
            random.shuffle(inv.deck)
        ctx.extra["all_in_drawn"] = len(drawn)
        ctx.extra["all_in_weaknesses_returned"] = len(weaknesses)
        ctx.game_state.log_effect(
            f"🃏 孤注一掷：超出{margin}点，抽{len(drawn)}张牌"
            + (f"，{len(weaknesses)}张弱点洗回牌堆" if weaknesses else ""))
