"""Dream Parasite (Level 0) — Neutral Skill, Weakness. Bonded (Nightmare Bauble).
当梦寄生在你手牌中时，你必须将它投入到你进行的下一个技能检定（如果可以）。
本技能的图标从你的技能值中减去，而非增加。
若本次技能检定失败，受到1点伤害和1点恐惧。

简化说明：
- "必须投入下一个检定"由会话层在构建 committed_cards 时强制（引擎缺口，
  投入列表由调用方给出）。
- 图标反转为负：SKILL_TEST_COMMIT 时引擎已按 skill_icons（wild×2）加算，
  本实现修正 -2×图标数（净效果为 -2）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class DreamParasite(CardImplementation):
    card_id = "dream_parasite_lv0"

    @on_event(GameEvent.SKILL_TEST_COMMIT, priority=TimingPriority.WHEN)
    def icons_subtract(self, ctx):
        """本技能的图标从技能值中减去而非增加。"""
        if "dream_parasite_lv0" not in (ctx.committed_cards or []):
            return
        cd = ctx.game_state.get_card_data("dream_parasite_lv0")
        icons = sum((cd.skill_icons or {}).values()) if cd else 0
        if icons:
            # 引擎已 +icons；修正 -2×icons 使净效果为 -icons
            ctx.modify_amount(-2 * icons, "dream_parasite_negative_icons")
            ctx.extra["dream_parasite_icons"] = -icons

    @on_event(GameEvent.SKILL_TEST_FAILED, priority=TimingPriority.AFTER)
    def damage_and_horror_on_failure(self, ctx):
        """若本次技能检定失败，受到1点伤害和1点恐惧。"""
        if "dream_parasite_lv0" not in (ctx.committed_cards or []):
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        inv.damage += 1  # 直接伤害/恐惧（不分配）
        inv.horror += 1
        ctx.extra["dream_parasite_suffered"] = True
        ctx.game_state.log_effect("😱 梦寄生：检定失败，受1点伤害和1点恐惧")
