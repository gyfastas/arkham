"""Winging It (Level 0) — Survivor Event. (04272)
你可以从你弃牌堆打出将就一下。如果你这么做，结算效果后将其洗回你的牌堆。
调查。这次调查中，你所在地点隐藏值-1。（如果你从你的弃牌堆打出将就一下，
并且调查成功，发现1个额外的线索。）

简化说明：
- "从弃牌堆打出"由会话层提供入口，并经 ctx.extra["from_discard_pile"]=True
  告知；默认按从手牌打出处理。从弃牌堆打出时：结算后（本次调查结束的
  SKILL_TEST_ENDS）从弃牌堆取回并随机洗入牌堆（引擎 _play_event 会在
  CARD_PLAYED 后把事件放入弃牌堆，故在检定结束时取回）。
- "调查"动作本身由会话层在打出后发起；本实现武装"下一次智力检定难度-1"
  （同 lantern/flashlight 的武装口径，仅对打出者的下一次智力检定生效）。
- 额外线索沿用 deduction 的 CLUE_DISCOVERED 通道（真实调查有基础发现才发）。
"""

import random

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class WingingIt(CardImplementation):
    card_id = "winging_it_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._owner: str | None = None
        self._shroud_armed = False
        self._from_discard = False
        self._clue_pending = False

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def on_played(self, ctx):
        """打出时：武装隐藏值-1；记录是否从弃牌堆打出。"""
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        self._owner = inv.investigator_id
        self._shroud_armed = True
        self._from_discard = bool(ctx.extra.get("from_discard_pile"))
        ctx.game_state.log_effect("🎯 将就一下：本次调查所在地点隐藏值-1")

    @on_event(GameEvent.SKILL_TEST_BEGINS, priority=TimingPriority.WHEN)
    def lower_shroud(self, ctx):
        """本次调查（打出者的下一次智力检定）：难度-1。"""
        if not self._shroud_armed or ctx.investigator_id != self._owner:
            return
        if ctx.skill_type != Skill.INTELLECT:
            return
        if ctx.difficulty is not None and ctx.difficulty > 0:
            ctx.difficulty = max(0, ctx.difficulty - 1)
            ctx.extra["winging_it_lowered"] = True
        self._shroud_armed = False

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.AFTER)
    def mark_extra_clue(self, ctx):
        """从弃牌堆打出且调查成功：标记额外线索。"""
        if ctx.investigator_id != self._owner or not self._from_discard:
            return
        if ctx.skill_type != Skill.INTELLECT:
            return
        self._clue_pending = True

    @on_event(GameEvent.CLUE_DISCOVERED, priority=TimingPriority.AFTER)
    def take_extra_clue(self, ctx):
        """基础发现结算后（确认是调查）：再发现1条线索。"""
        if not self._clue_pending or ctx.investigator_id != self._owner:
            return
        self._clue_pending = False
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        location = ctx.game_state.get_location(inv.location_id)
        if location is not None and location.clues > 0:
            location.clues -= 1
            inv.clues += 1
            ctx.game_state.log_effect("🎯 将就一下：额外发现1个线索")

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def reshuffle(self, ctx):
        """结算后：若从弃牌堆打出，洗回牌堆而非留在弃牌堆。"""
        if ctx.investigator_id != self._owner:
            return
        try:
            if not self._from_discard:
                return
            inv = ctx.game_state.get_investigator(ctx.investigator_id)
            if inv is None or self.card_id not in inv.discard:
                return
            inv.discard.remove(self.card_id)
            idx = random.randint(0, len(inv.deck))
            inv.deck.insert(idx, self.card_id)
            ctx.extra["winging_it_reshuffled"] = True
            ctx.game_state.log_effect("🎯 将就一下：洗回牌堆")
        finally:
            self._from_discard = False
            self._clue_pending = False
