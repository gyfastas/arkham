"""Occult Scraps (Level 0) — Neutral Asset, Weakness.
神秘残页不能使用打出行动打出。
神秘残页在你手中时，你获得-2[意志]。
神秘残页在场时，你获得-1[意志]。

简化说明：
- "不能使用打出行动打出"由会话层在打出校验时过滤（引擎 _play 无卡牌级
  打出限制钩子）。
- 在手牌中的持续效果依赖 persistent_in_hand（draw_hooks 保持注册）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class OccultScraps(CardImplementation):
    card_id = "occult_scraps_lv0"
    persistent_in_hand = True  # 在手牌中持续生效（-2意志）

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def willpower_penalty(self, ctx):
        if ctx.skill_type != Skill.WILLPOWER:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if self.instance_id in inv.play_area:
            ctx.modify_amount(-1, "occult_scraps_in_play")
        elif "occult_scraps_lv0" in inv.hand:
            ctx.modify_amount(-2, "occult_scraps_in_hand")
