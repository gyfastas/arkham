"""Shotgun (Level 4) — Guardian Asset, Hand x2.
使用(2弹药)。[行动]花费1弹药：攻击。本次攻击你获得+3战斗。
本次攻击不造成标准伤害，改为造成等同于你成功超出点数的伤害
（最少1点，最多5点）。如果你失败且将误伤另一位调查员，
本次攻击对改为你失败点数的伤害（最少1点，最多5点）。

简化说明：
- 弹药在命中时扣除（与 .45自动手枪 一致；引擎没有发起攻击时的扣费通道）。
- 弹药为0时攻击加成不生效（等同徒手攻击）；引擎层无法阻止发起攻击本身。
- 失手误伤流程引擎未实现（当前引擎不会误伤调查员），失败分支天然无效果。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class Shotgun(CardImplementation):
    card_id = "shotgun_lv4"

    def _has_ammo(self, game_state) -> bool:
        card = game_state.get_card_instance(self.instance_id)
        return card is not None and card.uses.get("ammo", 0) > 0

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def combat_bonus(self, ctx):
        """用霰弹枪攻击时 +3 战斗（需有弹药）。"""
        if ctx.skill_type != Skill.COMBAT:
            return
        if ctx.source != self.instance_id:
            return
        if not self._has_ammo(ctx.game_state):
            return
        ctx.modify_amount(3, "shotgun_combat_bonus")

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.AFTER)
    def variable_damage(self, ctx):
        """成功时：伤害 = 成功超出点数（下限1上限5），替代标准伤害。"""
        if ctx.source != self.instance_id:
            return
        if ctx.skill_type != Skill.COMBAT:
            return
        if not self._has_ammo(ctx.game_state):
            return
        succeed_by = (ctx.modified_skill or 0) - (ctx.difficulty or 0)
        damage = min(max(succeed_by, 1), 5)
        # bonus_damage 通道在标准伤害(1)之上追加；设为 damage-1 使总伤害=damage，
        # 其他 +伤害 效果（如致命打击）在此基础上正常叠加。
        ctx.extra["bonus_damage"] = ctx.extra.get("bonus_damage", 0) + damage - 1
        ctx.extra["shotgun_damage"] = damage

    @on_event(GameEvent.DAMAGE_DEALT, priority=TimingPriority.WHEN)
    def spend_ammo(self, ctx):
        """攻击命中：扣1弹药（简化：未命中不扣）。"""
        if ctx.source != self.instance_id:
            return
        card = ctx.game_state.get_card_instance(self.instance_id)
        if card is not None and card.uses.get("ammo", 0) > 0:
            card.uses["ammo"] -= 1
            ctx.extra["shotgun_ammo_spent"] = True
