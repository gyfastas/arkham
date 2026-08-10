"""Able Bodied (Level 0) — Survivor Skill.
只要你控制的[[道具]]支援卡不超过2张，体格强健获得[战斗][敏捷]
（不超过1张时，改为获得[战斗][战斗][敏捷][敏捷]）。

简化说明：
- 印刷图标为[战斗][敏捷]；加值图标仅在被检定技能为战斗/敏捷时计入
  （引擎只统计与检定技能匹配的图标，故此处等价于官方结算）。
- "控制的道具支援卡"统计控制者游戏区中 traits 含 item 的支援卡实例。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class AbleBodied(CardImplementation):
    card_id = "able_bodied_lv0"

    @on_event(GameEvent.SKILL_TEST_COMMIT, priority=TimingPriority.WHEN)
    def bonus_icons(self, ctx):
        """道具≤2张：+1图标；≤1张：+2图标（仅战斗/敏捷检定）。"""
        if self.card_id not in ctx.committed_cards:
            return
        if ctx.skill_type not in (Skill.COMBAT, Skill.AGILITY):
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        items = 0
        for iid in inv.play_area:
            inst = ctx.game_state.get_card_instance(iid)
            if inst is None:
                continue
            cd = ctx.game_state.get_card_data(inst.card_id)
            if cd is not None and "item" in [t.lower() for t in (cd.traits or [])]:
                items += 1
        if items > 2:
            return
        bonus = 2 if items <= 1 else 1
        ctx.modify_amount(bonus, "able_bodied_items")
        ctx.extra["able_bodied_bonus"] = bonus
        ctx.game_state.log_effect(
            f"💪 体格强健：控制{items}张道具支援卡，本次检定+{bonus}图标")
