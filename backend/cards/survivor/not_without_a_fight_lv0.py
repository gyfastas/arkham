"""\"Not without a fight!\" (Level 0) — Survivor Skill.
你与敌人交战时才可投入技能检定。
你每与一个敌人交战，"放马过来！"获得[意志][战斗][敏捷]。

简化说明：
- 加图标挂 SKILL_TEST_COMMIT：每个与你交战的敌人为本次检定+1图标
  （意志/战斗/敏捷各+1，对被检定的技能恒为+1/敌人）。
- "与敌人交战时才可投入"为投入限制：引擎无投入校验钩子，无法阻止
  未交战时投入（此时仅按印刷图标生效，不获得加值）——引擎缺口，见报告。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class NotWithoutAFight(CardImplementation):
    card_id = "not_without_a_fight_lv0"

    @on_event(GameEvent.SKILL_TEST_COMMIT, priority=TimingPriority.WHEN)
    def icons_per_engaged_enemy(self, ctx):
        """每个与你交战的敌人：本卡额外获得1组图标（本次检定+1）。"""
        if self.card_id not in ctx.committed_cards:
            return
        engaged = ctx.game_state.get_engaged_enemies(ctx.investigator_id)
        count = len(engaged)
        if count <= 0:
            return
        ctx.modify_amount(count, "not_without_a_fight_engaged")
        ctx.extra["not_without_a_fight_enemies"] = count
        ctx.game_state.log_effect(
            f"👊 放马过来！：与{count}个敌人交战，本次检定+{count}图标")
