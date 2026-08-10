"""Essence of the Dream (Level 0) — Seeker Skill. (06113)
绑定(梦境日记)。
在梦的本质将要进入你的弃牌堆或被混洗入你的牌堆时，改为将其放在一边，
位于场外（与你的绑定卡牌一起）。

简化说明：
- 主要结算路径为"投入技能检定后进入弃牌堆"：SKILL_TEST_ENDS 时若本卡
  在本次检定中被投入（ST.2 已将其丢入弃牌堆），改置 scenario.vars["set_aside"]
  （与绑定卡共同场外存放）；
- 引擎缺口：CARD_DISCARDED 事件已定义但全引擎无发射点，因此从手牌被效果
  丢弃、牌堆混洗等其它路径暂不拦截（见报告）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class EssenceOfTheDream(CardImplementation):
    card_id = "essence_of_the_dream_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._committed_by: str | None = None

    @on_event(GameEvent.SKILL_TEST_COMMIT, priority=TimingPriority.AFTER)
    def track_commit(self, ctx):
        """本卡被投入检定：记录执行者，等待检定结束时拦截弃置。"""
        if self.card_id in (ctx.committed_cards or []):
            self._committed_by = ctx.investigator_id

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def set_aside_instead_of_discard(self, ctx):
        """投入后进入弃牌堆时：改为放在一边，位于场外。"""
        if self._committed_by is None:
            return
        inv_id, self._committed_by = self._committed_by, None
        inv = ctx.game_state.get_investigator(inv_id)
        if inv is None or self.card_id not in inv.discard:
            return
        inv.discard.remove(self.card_id)
        ctx.game_state.scenario.vars.setdefault("set_aside", []).append(self.card_id)
        ctx.extra["essence_of_the_dream_set_aside"] = True
        ctx.game_state.log_effect("🌙 梦的本质：不进入弃牌堆，改为放在一边（场外）")
