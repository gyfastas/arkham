""".25 Automatic (Level 0) — Rogue Asset, Hand slot. (07025)
快速。使用(4子弹)。
[行动]花费1子弹：攻击。如果攻击的敌人已横置，这次攻击你+2战斗并造成+1伤害。

简化说明：
- 子弹在发起攻击时（FIGHT_ACTION_INITIATED）扣除，无子弹时取消攻击
  （lupara 同模式，official 时机）。
- "敌人已横置"在发起攻击时判定并锁定（SKILL_TEST 事件不带 enemy_id）。
- +1伤害经 ctx.extra["bonus_damage"] 通道汇入战斗结算。
- 数据注记：JSON 的 fast 字段为 null，卡面文本为"快速"；快速由数据/会话层负责。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class TwentyFiveAutomaticLv0(CardImplementation):
    card_id = "25_automatic_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._attack_paid = False
        self._target_exhausted = False

    @on_event(GameEvent.FIGHT_ACTION_INITIATED, priority=TimingPriority.WHEN)
    def spend_ammo(self, ctx):
        """花费1子弹：攻击。无子弹时攻击被取消（不花费行动）。"""
        if ctx.source != self.instance_id:
            return
        card = ctx.game_state.get_card_instance(self.instance_id)
        if card is None:
            return
        if card.uses.get("ammo", 0) < 1:
            self._attack_paid = False
            self._target_exhausted = False
            ctx.cancel()
            ctx.game_state.log_effect("🔫 .25自动手枪：没有子弹，攻击取消")
            return
        card.uses["ammo"] -= 1
        self._attack_paid = True
        enemy = ctx.game_state.get_card_instance(ctx.enemy_id) if ctx.enemy_id else None
        self._target_exhausted = bool(enemy is not None and enemy.exhausted)

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def combat_bonus(self, ctx):
        """攻击已横置敌人：+2战斗。"""
        if ctx.source != self.instance_id or not self._attack_paid:
            return
        if ctx.skill_type != Skill.COMBAT or not self._target_exhausted:
            return
        ctx.modify_amount(2, "25_automatic_exhausted_bonus")

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.AFTER)
    def bonus_damage(self, ctx):
        """攻击已横置敌人：+1伤害（经 bonus_damage 通道结算）。"""
        if ctx.source != self.instance_id or not self._attack_paid:
            return
        if ctx.skill_type != Skill.COMBAT or not self._target_exhausted:
            return
        ctx.extra["bonus_damage"] = int(ctx.extra.get("bonus_damage", 0) or 0) + 1

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear_attack_state(self, ctx):
        if ctx.source == self.instance_id:
            self._attack_paid = False
            self._target_exhausted = False
