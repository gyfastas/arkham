"""Practice Makes Perfect (Level 0) — Seeker Event, Fast. (06197)
快速。在你所在地点的技能检定中打出。
在你的牌堆顶部9张卡牌中查找一张[[精通]]技能卡，并将其投入这次技能
检定(如可能)。将其余卡牌混洗回你的牌堆。在这次检定结束后，如果检定
成功，不将该技能卡丢弃，改为将其加入你的手牌。

简化说明：
- 检索选择简化为自动取顶9张中第一张[[精通]]技能卡，可用
  ctx.extra["search_pick"] 指定（玩家选择 UI 需会话层接线）；
- 找到的精通卡"投入"以技能图标加值实现（SKILL_VALUE_DETERMINED 按检定
  技能补加匹配+wild 图标）；精通卡自身的投入效果不激活（引擎对非手牌
  投入无支持，引擎缺口见报告）；
- 若打出时无进行中的检定，加值作用于你的下一次技能检定，回合结束过期；
  检定结束：成功→精通卡入手，失败/过期→弃置。
"""

import random

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import CardType, GameEvent, TimingPriority

SEARCH_DEPTH = 9


class PracticeMakesPerfect(CardImplementation):
    card_id = "practice_makes_perfect_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._skill_card: str | None = None  # 找到并投入的精通技能卡
        self._owner_id: str | None = None
        self._boost_used = False

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def search_and_commit(self, ctx):
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or not inv.deck:
            return

        depth = min(SEARCH_DEPTH, len(inv.deck))
        looked = list(inv.deck[:depth])
        rest = list(inv.deck[depth:])

        pick = ctx.extra.get("search_pick")
        if pick not in looked or not self._is_practiced_skill(ctx, pick):
            pick = next(
                (c for c in looked if self._is_practiced_skill(ctx, c)), None)
        if pick is None:
            ctx.extra["practice_makes_perfect_failed"] = "no_practiced"
            return

        looked.remove(pick)
        inv.deck = rest + looked
        random.shuffle(inv.deck)
        self._skill_card = pick
        self._owner_id = inv.investigator_id
        self._boost_used = False
        ctx.extra["practice_makes_perfect_committed"] = pick
        ctx.game_state.log_effect(
            f"🎯 熟能生巧：从牌堆顶{depth}张找到"
            f"【{ctx.game_state.card_name(pick)}】投入本次检定，牌堆洗混"
        )

    @staticmethod
    def _is_practiced_skill(ctx, card_id) -> bool:
        cd = ctx.game_state.get_card_data(card_id)
        return (
            cd is not None
            and cd.type == CardType.SKILL
            and "practiced" in (cd.traits or [])
        )

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def committed_icons(self, ctx):
        """投入的精通卡图标：按检定技能补加匹配+wild 图标（一次性）。"""
        if not self._skill_card or self._boost_used:
            return
        if ctx.investigator_id != self._owner_id:
            return
        cd = ctx.game_state.get_card_data(self._skill_card)
        if cd is None or ctx.skill_type is None:
            return
        icons = cd.skill_icons or {}
        bonus = icons.get(ctx.skill_type.value, 0) + icons.get("wild", 0)
        self._boost_used = True
        if bonus > 0:
            ctx.modify_amount(bonus, "practice_makes_perfect_icons")

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def resolve_committed_skill(self, ctx):
        """检定结束：成功则精通卡加入手牌，失败则弃置。"""
        if not self._skill_card or ctx.investigator_id != self._owner_id:
            return
        inv = ctx.game_state.get_investigator(self._owner_id)
        card = self._skill_card
        self._skill_card = None
        self._owner_id = None
        if inv is None:
            return
        if ctx.success:
            inv.hand.append(card)
            ctx.extra["practice_makes_perfect_returned"] = card
            ctx.game_state.log_effect(
                f"🎯 熟能生巧：检定成功，【{ctx.game_state.card_name(card)}】加入手牌")
        else:
            inv.discard.append(card)

    @on_event(GameEvent.INVESTIGATOR_TURN_ENDS, priority=TimingPriority.AFTER)
    def expire(self, ctx):
        """打出后无检定发生：回合结束时找到的精通卡弃置。"""
        if not self._skill_card:
            return
        inv = ctx.game_state.get_investigator(self._owner_id)
        if inv is not None:
            inv.discard.append(self._skill_card)
        self._skill_card = None
        self._owner_id = None
