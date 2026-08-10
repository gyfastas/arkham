""".45 Automatic (Level 2) — Guardian Asset, Hand slot. (03190)
使用(4子弹)。[行动]花费1子弹：攻击。本次攻击你+2战斗、造成+1伤害，
本次攻击忽略反击关键词。

实现说明：
- 弹药在 FIGHT_ACTION_INITIATED（以本武器发起攻击）时支付（官方时机；
  未命中同样消耗）；无弹药时取消攻击。
- "忽略反击"：引擎在攻击失败时直接检查敌人 keywords，无忽略通道，
  故在发起攻击时临时从敌人卡牌数据移除 retaliate，检定结束后还原
  （CardData 按 card_id 共享，攻击窗口内同名敌人一同忽略反击，特此注明）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class FortyFiveAutomaticLv2(CardImplementation):
    card_id = "45_automatic_lv2"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._attack_paid = False
        self._stripped_data = None  # 被临时移除 retaliate 的 CardData

    @on_event(GameEvent.FIGHT_ACTION_INITIATED, priority=TimingPriority.WHEN)
    def pay_ammo(self, ctx):
        """发起攻击时花费1子弹；无子弹则无法以本武器攻击。"""
        self._attack_paid = False
        if ctx.source != self.instance_id:
            return
        card = ctx.game_state.get_card_instance(self.instance_id)
        if card is None or card.uses.get("ammo", 0) <= 0:
            ctx.cancel()
            ctx.game_state.log_effect("🔫 .45自动手枪：没有子弹，无法攻击")
            return
        card.uses["ammo"] -= 1
        self._attack_paid = True

        # 本次攻击忽略反击：临时移除敌人的 retaliate 关键词
        enemy = ctx.game_state.get_card_instance(ctx.enemy_id) if ctx.enemy_id else None
        enemy_data = ctx.game_state.get_card_data(enemy.card_id) if enemy else None
        if enemy_data is not None and "retaliate" in (enemy_data.keywords or []):
            enemy_data.keywords.remove("retaliate")
            self._stripped_data = enemy_data

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def combat_bonus(self, ctx):
        """已付子弹的攻击 +2 战斗。"""
        if ctx.source != self.instance_id or not self._attack_paid:
            return
        if ctx.skill_type == Skill.COMBAT:
            ctx.modify_amount(2, "45_automatic_lv2_combat_bonus")

    @on_event(GameEvent.DAMAGE_DEALT, priority=TimingPriority.WHEN)
    def extra_damage(self, ctx):
        """已付子弹的攻击造成 +1 伤害。"""
        if ctx.source != self.instance_id or not self._attack_paid:
            return
        ctx.modify_amount(1, "45_automatic_lv2_extra_damage")

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear_flag(self, ctx):
        self._attack_paid = False
        if self._stripped_data is not None:
            # 还原反击关键词
            if "retaliate" not in (self._stripped_data.keywords or []):
                self._stripped_data.keywords.append("retaliate")
            self._stripped_data = None
