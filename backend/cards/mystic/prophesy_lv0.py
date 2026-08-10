"""Prophesy (Level 0) — Mystic Skill. (1 wild icon)
当场上有3个或更多毁灭时，预言获得[wild]（当场上有6个或更多毁灭时，
改为获得[wild][wild]）。

简化说明：
- 图标为动态值：SKILL_TEST_COMMIT 时按 total_doom_in_play() 追加投入图标数
  （基础的1个[wild]由卡面数据 skill_icons 自动结算）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class Prophesy(CardImplementation):
    card_id = "prophesy_lv0"

    @on_event(GameEvent.SKILL_TEST_COMMIT, priority=TimingPriority.WHEN)
    def doom_icons(self, ctx):
        if self.card_id not in (ctx.committed_cards or []):
            return
        doom = ctx.game_state.total_doom_in_play()
        bonus = 2 if doom >= 6 else (1 if doom >= 3 else 0)
        if bonus:
            ctx.modify_amount(bonus, f"{self.card_id}_doom_icons")
            ctx.extra[f"{self.card_id}_bonus_icons"] = bonus
