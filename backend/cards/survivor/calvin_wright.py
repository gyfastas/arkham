"""Calvin Wright — Survivor Investigator.
能力：每有1点恐惧在你身上，你获得+1[willpower]和+1[intellect]。
每有1点伤害在你身上，你获得+1[combat]和+1[agility]。
远古印记：+0。你可以治愈1点伤害或恐惧，或受到1点直接伤害或直接恐惧。

简化说明：
- 技能加值经 SKILL_VALUE_DETERMINED 按当前伤害/恐惧即时结算（与
  beat_cop 等同通道；对 preview_skill_bonuses 的干跑无副作用）。
- 远古印记的四选一：同步检定流程无法等待玩家选择，经
  scenario.vars["calvin_wright_elder_choice"] 预设
  （"heal_damage" / "heal_horror" / "take_damage" / "take_horror"）；
  缺省自动选择：有伤害先治愈1伤害，否则有恐惧治愈1恐惧，都没有则不结算
  （不主动自残）。"take_*"为直接伤害/恐惧，不经分配/取消窗口。
- 马泰奥神父将自动失败转为远古印记时（father_mateo_converted 标记），本卡
  同样按远古印记结算。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import (
    ChaosTokenType, GameEvent, Skill, TimingPriority,
)


class CalvinWright(CardImplementation):
    card_id = "calvin_wright"

    def _get_calvin(self, game_state, investigator_id):
        """Return the investigator state iff it is Calvin Wright."""
        if investigator_id is None:
            return None
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return None
        card_data = getattr(inv, "card_data", None)
        if card_data is None or card_data.id != "calvin_wright":
            return None
        return inv

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def skill_bonus(self, ctx):
        """每点恐惧 +1意志/+1智力；每点伤害 +1战斗/+1敏捷。"""
        inv = self._get_calvin(ctx.game_state, ctx.investigator_id)
        if inv is None:
            return
        if ctx.skill_type in (Skill.WILLPOWER, Skill.INTELLECT):
            bonus = inv.horror
        elif ctx.skill_type in (Skill.COMBAT, Skill.AGILITY):
            bonus = inv.damage
        else:
            bonus = 0
        if bonus:
            ctx.modify_amount(bonus, "calvin_wright_ability")

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.WHEN)
    def elder_sign_effect(self, ctx):
        """远古印记：+0。治愈1伤害/恐惧，或受1直接伤害/恐惧（四选一）。"""
        if ctx.chaos_token != ChaosTokenType.ELDER_SIGN \
                and not ctx.extra.get("father_mateo_converted"):
            return
        inv = self._get_calvin(ctx.game_state, ctx.investigator_id)
        if inv is None:
            return

        scenario = getattr(ctx.game_state, "scenario", None)
        choice = scenario.vars.get("calvin_wright_elder_choice") \
            if scenario is not None else None
        if choice is None:
            if inv.damage > 0:
                choice = "heal_damage"
            elif inv.horror > 0:
                choice = "heal_horror"

        if choice == "heal_damage" and inv.damage > 0:
            inv.damage -= 1
            ctx.game_state.log_effect("🩹 加尔文·怀特：远古印记，治愈1点伤害")
        elif choice == "heal_horror" and inv.horror > 0:
            inv.horror -= 1
            ctx.game_state.log_effect("🩹 加尔文·怀特：远古印记，治愈1点恐惧")
        elif choice == "take_damage":
            inv.damage += 1
            ctx.game_state.log_effect("🩸 加尔文·怀特：远古印记，受到1点直接伤害")
        elif choice == "take_horror":
            inv.horror += 1
            ctx.game_state.log_effect("🩸 加尔文·怀特：远古印记，受到1点直接恐惧")
