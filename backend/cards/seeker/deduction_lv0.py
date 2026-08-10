"""Deduction (Level 0) — Seeker Skill.
如果本次检定在调查地点时成功，在该地点额外发现1条线索。

官方结算顺序：调查行动的基础发现先结算（ST.7 发出 CLUE_DISCOVERED），
推理的额外线索在其后（"additional"）。
实现：ST.6（SKILL_TEST_SUCCESSFUL）打标记 → 基础发现的 CLUE_DISCOVERED
（AFTER，确认这是调查行动且基础结算已完成）再取额外线索。
说明：
- 投入的技能卡实例在 ST.2 才被激活，收不到行动前的
  INVESTIGATE_ACTION_INITIATED；因此"调查时"条件以基础发现的
  CLUE_DISCOVERED 为准——非调查的智力检定（如诡计卡检定）不发该事件，
  自然不会发线索；
- 地点只剩1条线索时由基础发现先拿（此前实现推理在 ST.6 抢线索，导致
  基础发现落空、CLUE_DISCOVERED 不触发）；
- 调查成功但地点已无线索（无基础发现）时，推理也不发线索。
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
        GameEvent.CLUE_DISCOVERED,
        priority=TimingPriority.AFTER,
    )
    def take_extra_clue(self, ctx):
        """基础发现结算后（确认是调查）：若地点还有线索，再发现1条。"""
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

    @on_event(
        GameEvent.SKILL_TEST_ENDS,
        priority=TimingPriority.AFTER,
    )
    def clear_flag(self, ctx):
        """检定结束：清除未消费的标记（如非调查检定/失败）。"""
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is not None and hasattr(inv, "active_effects"):
            inv.active_effects.pop(_FLAG, None)
