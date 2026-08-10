"""Written in the Stars (Level 0) — Seeker Event, Fast. (08034)
快速。只能在你的回合中打出。
丢弃你牌堆顶部的卡牌。如果该卡牌为弱点，将其混洗回你的牌堆。否则在
你的回合剩余时间内，只要该卡牌在你的弃牌堆中，将其投入到你执行的
每个符合条件的技能检定中。

简化说明：
- "投入到每个符合条件的技能检定"：该卡在弃牌堆期间，你执行的每次
  检定按其图标（匹配检定技能 + wild）补加投入图标；无匹配图标（不符合
  条件）时不补加；卡牌自身不离开弃牌堆，其投入效果不激活（引擎缺口，
  与熟能生巧一致）；
- 你的回合结束（INVESTIGATOR_TURN_ENDS）效果过期。
"""

import random

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority
from backend.models.state import is_weakness_card


class WrittenInTheStars(CardImplementation):
    card_id = "written_in_the_stars_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._card: str | None = None  # 被丢弃、待投入的牌
        self._owner_id: str | None = None

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def discard_top(self, ctx):
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or not inv.deck:
            return
        top = inv.deck.pop(0)
        cd = ctx.game_state.get_card_data(top)
        if is_weakness_card(cd):
            # 弱点：混洗回牌堆
            inv.deck.append(top)
            random.shuffle(inv.deck)
            ctx.extra["written_in_the_stars_weakness"] = top
            ctx.game_state.log_effect(
                f"✨ 繁星密语：弃到弱点【{ctx.game_state.card_name(top)}】，混洗回牌堆")
            return
        inv.discard.append(top)
        self._card = top
        self._owner_id = inv.investigator_id
        ctx.extra["written_in_the_stars_card"] = top
        ctx.game_state.log_effect(
            f"✨ 繁星密语：【{ctx.game_state.card_name(top)}】在本回合"
            "投入到你的每个符合条件的检定")

    @on_event(GameEvent.SKILL_TEST_COMMIT, priority=TimingPriority.WHEN)
    def commit_discarded_card(self, ctx):
        """弃牌堆中的牌投入到你的每个符合条件的检定（按图标补加）。"""
        if not self._card or ctx.investigator_id != self._owner_id:
            return
        inv = ctx.game_state.get_investigator(self._owner_id)
        if inv is None or self._card not in inv.discard:
            return
        cd = ctx.game_state.get_card_data(self._card)
        if cd is None or ctx.skill_type is None:
            return
        icons = cd.skill_icons or {}
        bonus = icons.get(ctx.skill_type.value, 0) + icons.get("wild", 0)
        if bonus > 0:
            ctx.modify_amount(bonus, "written_in_the_stars_icons")
            ctx.extra["written_in_the_stars_committed"] = self._card

    @on_event(GameEvent.INVESTIGATOR_TURN_ENDS, priority=TimingPriority.AFTER)
    def expire(self, ctx):
        self._card = None
        self._owner_id = None
