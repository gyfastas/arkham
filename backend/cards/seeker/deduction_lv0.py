"""Deduction (Level 0) — Seeker Skill.
提交到智力检定时提供1个智力图标。如果该检定成功，额外发现1条线索。

官方结算顺序：调查行动的基础发现先结算（ST.7），推理的额外线索在其后。
此前实现挂在 SKILL_TEST_SUCCESSFUL（ST.6，先于基础结算），当地点只剩
1条线索时推理会"抢走"基础线索——基础效果拿不到、CLUE_DISCOVERED 不
触发（米兰博士等后续效应失效）。
现改为：ST.6 打标记 → ST.8（SKILL_TEST_ENDS，基础结算之后）再取额外线索。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority

_FLAG = "deduction_lv0_extra_clue"


class Deduction(CardImplementation):
    card_id = "deduction_lv0"

    @on_event(
        GameEvent.SKILL_TEST_SUCCESSFUL,
        priority=TimingPriority.AFTER,
    )
    def mark_extra_clue(self, ctx):
        """智力检定成功且投入了推理 → 标记待取的额外线索。"""
        if "deduction_lv0" not in (ctx.committed_cards or []):
            return
        if ctx.skill_type != Skill.INTELLECT:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if not hasattr(inv, "active_effects"):
            inv.active_effects = {}
        inv.active_effects[_FLAG] = True

    @on_event(
        GameEvent.SKILL_TEST_ENDS,
        priority=TimingPriority.AFTER,
    )
    def take_extra_clue(self, ctx):
        """基础结算完成后：若地点还有线索，再发现1条（地点线索不为负）。"""
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        effects = getattr(inv, "active_effects", None) or {}
        if not effects.pop(_FLAG, False):
            return
        location = ctx.game_state.get_location(inv.location_id)
        if location is not None and location.clues > 0:
            location.clues -= 1
            inv.clues += 1
