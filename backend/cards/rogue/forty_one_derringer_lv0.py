""".41 Derringer (Level 0) — Rogue Asset, Hand slot.
使用(3弹药)。[行动]花费1弹药：攻击。本次攻击你获得+2战斗。
若你成功且超出难度2点以上，本次攻击造成+1伤害。

简化说明：
- 弹药在命中时扣除（与 .45自动手枪 一致；官方为发起攻击时花费）。
- margin 伤害在 SKILL_TEST_SUCCESSFUL 检查 margin>=2，
  写入 ctx.extra["bonus_damage"] 由引擎结算。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class FortyOneDerringer(CardImplementation):
    card_id = "forty_one_derringer_lv0"
    extra_damage_on_margin = 2  # lv2 覆盖为 1

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def combat_bonus(self, ctx):
        if ctx.skill_type != Skill.COMBAT:
            return
        if ctx.source != self.instance_id:
            return
        ctx.modify_amount(2, f"{self.card_id}_combat_bonus")

    @on_event(GameEvent.DAMAGE_DEALT, priority=TimingPriority.WHEN)
    def spend_ammo(self, ctx):
        if ctx.source != self.instance_id:
            return
        card = ctx.game_state.get_card_instance(self.instance_id)
        if card is not None and card.uses.get("ammo", 0) > 0:
            card.uses["ammo"] -= 1

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.AFTER)
    def margin_damage(self, ctx):
        """成功且超出难度 N 点以上：本次攻击造成+1伤害。"""
        if ctx.source != self.instance_id:
            return
        if ctx.skill_type != Skill.COMBAT:
            return
        margin = (ctx.modified_skill or 0) - (ctx.difficulty or 0)
        if margin < self.extra_damage_on_margin:
            return
        ctx.extra["bonus_damage"] = int(ctx.extra.get("bonus_damage", 0) or 0) + 1
