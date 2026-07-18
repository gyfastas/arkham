""".41 Derringer (Level 0) — Rogue Asset, Hand slot.
使用(3弹药)。消耗.41短口手枪并花费1弹药：攻击。你获得+2战斗。
如果这次攻击击败该敌人，发现你所在地点1条线索。

简化说明：
- 弹药在命中时扣除（与 .45自动手枪 一致）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class FortyOneDerringer(CardImplementation):
    card_id = "forty_one_derringer_lv0"
    extra_damage_on_margin = None  # lv2 覆盖

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def combat_bonus(self, ctx):
        if ctx.skill_type != Skill.COMBAT:
            return
        if ctx.extra.get("weapon_card_id") != self.card_id and ctx.source != self.instance_id:
            return
        ctx.modify_amount(2, f"{self.card_id}_combat_bonus")

    @on_event(GameEvent.DAMAGE_DEALT, priority=TimingPriority.WHEN)
    def spend_ammo(self, ctx):
        if ctx.source != self.instance_id:
            return
        card = ctx.game_state.get_card_instance(self.instance_id)
        if card is not None and card.uses.get("ammo", 0) > 0:
            card.uses["ammo"] -= 1
            ctx.extra[f"{self.card_id}_hit"] = True

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.AFTER)
    def on_success(self, ctx):
        """lv2：成功超过难度2点以上，+1伤害。"""
        if self.extra_damage_on_margin is None:
            return
        if not ctx.extra.get(f"{self.card_id}_hit"):
            return
        if (ctx.modified_skill or 0) - (ctx.difficulty or 0) < self.extra_damage_on_margin:
            return
        enemy_id = ctx.enemy_id or ctx.extra.get("enemy_id")
        enemy = ctx.game_state.get_card_instance(enemy_id) if enemy_id else None
        if enemy is not None:
            enemy.damage += 1

    @on_event(GameEvent.ENEMY_DEFEATED, priority=TimingPriority.AFTER)
    def clue_on_defeat(self, ctx):
        """如果这次攻击击败该敌人：发现你所在地点1条线索。"""
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        # 仅当该敌人被本卡攻击击败（同一次检定命中过）
        if not ctx.extra.get(f"{self.card_id}_hit"):
            return
        loc = ctx.game_state.get_location(inv.location_id)
        if loc is not None and loc.clues > 0:
            loc.clues -= 1
            inv.clues += 1
            ctx.extra[f"{self.card_id}_clue"] = True
