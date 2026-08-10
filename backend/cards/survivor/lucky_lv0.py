"""Lucky! (Level 0) — Survivor Event.
快速。当你即将检定失败时打出，本次检定技能值+2（差值≤2时可转败为胜）。

简化说明：
- 从手牌中自动触发：检定失败时自动打出并应用 +2
  （官方为玩家自行选择打出时机；差值>2 时 +2 不足以翻转，结果仍为失败）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class Lucky(CardImplementation):
    card_id = "lucky_lv0"
    draw_a_card = False  # lv2 覆盖：打出后抽1张牌（无论成败）
    bonus = 2  # lv2 覆盖

    @on_event(GameEvent.SKILL_TEST_FAILED, priority=TimingPriority.WHEN)
    def turn_failure_to_success(self, ctx):
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.card_id not in inv.hand:
            return

        # 自动打出（简化：官方为玩家选择）
        cd = ctx.game_state.get_card_data(self.card_id)
        cost = (getattr(cd, "cost", 1) or 1) if cd else 1
        if inv.resources < cost:
            return
        inv.resources -= cost
        inv.hand.remove(self.card_id)
        inv.discard.append(self.card_id)

        # +N 技能值；差值≤N 时翻转结果，否则仍然失败
        margin = (ctx.difficulty or 0) - (ctx.modified_skill or 0)
        if margin <= self.bonus:
            ctx.success = True
            ctx.extra["lucky_turned_success"] = True
            ctx.game_state.log_effect(f"🍀 运气好！：+{self.bonus}技能值，检定失败转为成功")
        else:
            ctx.game_state.log_effect(
                f"🍀 运气好！：+{self.bonus}技能值（差{margin}点，仍失败）"
            )

        if self.draw_a_card and inv.deck:
            # lv2：抽1张牌（无论成败）
            inv.hand.append(inv.deck.pop(0))
            ctx.extra["lucky_drew"] = True
