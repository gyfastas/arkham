"""Sharp Vision (Level 1) — Survivor Skill. (06204)
每次技能检定最多投入1张。
只要在基础调查行动中投入目力敏锐，其获得 [intellect][intellect] 和以下文本：
"如果这次检定成功且超过难度至少2点，在此地点发现额外1个线索。"

简化说明：
- 投入的技能卡实现仅在检定流程（ST.2 起）内临时激活，看不到
  INVESTIGATE_ACTION_INITIATED（引擎检定上下文不带动作类型，引擎缺口），
  故 +2 图标的"基础调查行动"条件近似为智力检定（同 survival_instinct 的
  简化口径）；额外线索沿用 deduction 的 CLUE_DISCOVERED 通道——只有真实
  调查（产生基础发现）时才发放，非调查的智力检定自然不发线索。
- "每次检定最多投入1张"为投入窗口限制，由会话层约束。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority

_FLAG = "sharp_vision_lv1_extra_clue"


class SharpVision(CardImplementation):
    card_id = "sharp_vision_lv1"

    @on_event(GameEvent.SKILL_TEST_COMMIT, priority=TimingPriority.WHEN)
    def bonus_icons(self, ctx):
        """投入本卡的智力检定（基础调查）：+2 智力图标。"""
        if self.card_id not in (ctx.committed_cards or []):
            return
        if ctx.skill_type != Skill.INTELLECT:
            return
        ctx.modify_amount(2, "sharp_vision_icons")

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.AFTER)
    def mark_extra_clue(self, ctx):
        """成功且超出难度至少2点：标记待取的额外线索。"""
        if self.card_id not in (ctx.committed_cards or []):
            return
        if ctx.skill_type != Skill.INTELLECT:
            return
        margin = (ctx.modified_skill or 0) - (ctx.difficulty or 0)
        if margin < 2:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if not hasattr(inv, "active_effects"):
            inv.active_effects = {}
        inv.active_effects[_FLAG] = True

    @on_event(GameEvent.CLUE_DISCOVERED, priority=TimingPriority.AFTER)
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
            ctx.game_state.log_effect("👁 目力敏锐：超过难度2点，额外发现1个线索")

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear_flag(self, ctx):
        """检定结束：清除未消费的标记（如非调查检定/失败/超出不足2点）。"""
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is not None and hasattr(inv, "active_effects"):
            inv.active_effects.pop(_FLAG, None)
