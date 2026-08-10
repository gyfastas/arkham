"""Whispers from the Deep (Level 0) — Neutral Skill, Weakness (Curse).
本技能的图标从你的技能值中减去，而非增加。
强制 - 在选择一张卡牌放置于阿曼达·夏普下方时，如果深海低语在你手牌中：
你必须选择它。

简化说明：
- 图标反转在 SKILL_TEST_COMMIT 结算：引擎已把本卡图标计入正值，处理器
  再减去2倍图标数（净效果为减去图标）。经 persistent_in_hand=True 在
  手牌中保持注册，投入时无需会话层显式启用（弱点效果为强制）。
- 图标数按卡数据 skill_icons 中与检定技能匹配的图标 + 狂野图标计算
  （数据为 wild:1）。
- "必须选择它放置于阿曼达下方"依赖阿曼达·夏普的专属机制（引擎无对应
  区域），由 must_choose_beneath_amanda() 表达，供会话层查询（引擎缺口）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class WhispersFromTheDeep(CardImplementation):
    card_id = "whispers_from_the_deep_lv0"
    persistent_in_hand = True  # 手牌中保持注册，投入时强制生效

    @on_event(GameEvent.SKILL_TEST_COMMIT, priority=TimingPriority.WHEN)
    def icons_subtract(self, ctx):
        """本卡被投入持有者的检定时：其图标从技能值中减去而非增加。"""
        if "whispers_from_the_deep_lv0" not in (ctx.committed_cards or []):
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or "whispers_from_the_deep_lv0" not in inv.hand:
            return
        cd = ctx.game_state.get_card_data("whispers_from_the_deep_lv0")
        icons = 1  # 缺省 1 个狂野图标
        if cd is not None and cd.skill_icons:
            skill_key = ctx.skill_type.value if ctx.skill_type else ""
            icons = (cd.skill_icons.get(skill_key, 0)
                     + cd.skill_icons.get("wild", 0))
        if icons <= 0:
            return
        # 引擎已加 icons，再减 2*icons → 净效果 -icons
        ctx.modify_amount(-2 * icons, "whispers_from_the_deep_invert")
        ctx.game_state.log_effect("🌊 深海低语：投入的图标改为从技能值中减去")

    def must_choose_beneath_amanda(self, game_state, investigator_id) -> bool:
        """强制：本卡在手牌中时，放置于阿曼达·夏普下方必须选择它。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return False
        return "whispers_from_the_deep_lv0" in inv.hand
