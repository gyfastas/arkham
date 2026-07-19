"""Lucky! (Level 0) — Survivor Event.
快速。当你即将检定失败时，技能值+2（可使失败转为成功）。

简化说明：
- 从手牌中自动触发：你检定失败时自动打出并翻转结果
  （依赖 engine 对 ctx.success 的回读）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class Lucky(CardImplementation):
    card_id = "lucky_lv0"
    return_on_success = False  # lv2 覆盖

    @on_event(GameEvent.SKILL_TEST_FAILED, priority=TimingPriority.WHEN)
    def turn_failure_to_success(self, ctx):
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.card_id not in inv.hand:
            return

        # 自动打出
        cd = ctx.game_state.get_card_data(self.card_id)
        cost = getattr(cd, "cost", 1) or 1 if cd else 1
        if inv.resources < cost:
            return
        inv.resources -= cost
        inv.hand.remove(self.card_id)
        inv.discard.append(self.card_id)

        # +2 技能值并翻转结果
        ctx.success = True
        ctx.extra["lucky_turned_success"] = True
        ctx.game_state.log_effect("🍀 运气好！：检定失败转为成功")

        if self.return_on_success:
            # lv2：如果成功，返回运气好！到手中
            if self.card_id in inv.discard:
                inv.discard.remove(self.card_id)
                inv.hand.append(self.card_id)
                ctx.extra["lucky_returned"] = True
