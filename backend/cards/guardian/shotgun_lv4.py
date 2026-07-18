"""Shotgun (Level 4) — Guardian Asset, Hand x2.
使用(2弹药)。消耗霰弹枪并花费1弹药：攻击。本次攻击造成+2伤害。
如果你成功且超过难度2点以上，本次攻击造成额外+1伤害。

简化说明：
- 弹药在命中时扣除（与 .45自动手枪 一致）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class Shotgun(CardImplementation):
    card_id = "shotgun_lv4"

    @on_event(GameEvent.DAMAGE_DEALT, priority=TimingPriority.WHEN)
    def bonus_damage(self, ctx):
        """攻击命中：扣1弹药，+2伤害。"""
        if ctx.source != self.instance_id:
            return
        card = ctx.game_state.get_card_instance(self.instance_id)
        if card is None or card.uses.get("ammo", 0) <= 0:
            return
        card.uses["ammo"] -= 1
        ctx.modify_amount(2, "shotgun_bonus_damage")
        ctx.extra["shotgun_hit"] = True

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.AFTER)
    def extra_on_big_success(self, ctx):
        """成功超过难度2点以上：额外+1伤害。"""
        if not ctx.extra.get("shotgun_hit"):
            return
        if (ctx.modified_skill or 0) - (ctx.difficulty or 0) < 2:
            return
        enemy_id = ctx.enemy_id or ctx.extra.get("enemy_id")
        enemy = ctx.game_state.get_card_instance(enemy_id) if enemy_id else None
        if enemy is not None:
            enemy.damage += 1
            ctx.extra["shotgun_extra_damage"] = True
