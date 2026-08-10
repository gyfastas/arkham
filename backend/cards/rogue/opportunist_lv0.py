"""Opportunist (Level 0) — Rogue Skill.
仅可投入你正在执行的技能检定。
如果你成功且超出难度3点以上，在本检定后将机会主义者返回你的手牌，而非弃置。

实现说明：
- SKILL_TEST_SUCCESSFUL 时（ST.6）投入的卡仍在手牌中，ST.8 才弃置；
  因此先在成功时按 margin>=3 记录标记，再在 SKILL_TEST_ENDS
  （弃置已发生、临时实现尚未注销）从弃牌堆取回手牌。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class Opportunist(CardImplementation):
    card_id = "opportunist_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._return_pending = False

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.AFTER)
    def mark_return(self, ctx):
        if "opportunist_lv0" not in ctx.committed_cards:
            return
        margin = (ctx.modified_skill or 0) - (ctx.difficulty or 0)
        if margin >= 3:
            self._return_pending = True

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def return_to_hand(self, ctx):
        if not self._return_pending:
            return
        self._return_pending = False
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if "opportunist_lv0" in inv.discard:
            inv.discard.remove("opportunist_lv0")
            inv.hand.append("opportunist_lv0")
            ctx.extra["opportunist_returned"] = True
            ctx.game_state.log_effect("🔁 机会主义者：返回手牌")
