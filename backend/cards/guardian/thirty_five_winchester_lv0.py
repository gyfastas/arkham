""".35 Winchester (Level 0) — Guardian Asset, Hand x2. (06195)
使用(5弹药)。[行动]花费1弹药：攻击。本次攻击你获得+2战斗。
如果本次攻击中揭示了+1、0或[elder_sign]混乱标记，本次攻击造成+2伤害。

实现说明：
- 弹药在 FIGHT_ACTION_INITIATED（以本武器发起攻击）时支付（与 .45自动手枪
  lv2 一致；未命中同样消耗）；无弹药时取消攻击。
- 标记判定：CHAOS_TOKEN_RESOLVED 记录本次攻击揭示的标记，
  SKILL_TEST_SUCCESSFUL 时若为 +1/0/远古印记则经 bonus_damage 通道 +2 伤害。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import ChaosTokenType, GameEvent, Skill, TimingPriority

_BONUS_TOKENS = {
    ChaosTokenType.PLUS_1, ChaosTokenType.ZERO, ChaosTokenType.ELDER_SIGN,
}


class ThirtyFiveWinchester(CardImplementation):
    card_id = "35_winchester_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._attack_paid = False
        self._revealed_token = None

    @on_event(GameEvent.FIGHT_ACTION_INITIATED, priority=TimingPriority.WHEN)
    def pay_ammo(self, ctx):
        """发起攻击时花费1弹药；无弹药则无法以本武器攻击。"""
        self._attack_paid = False
        if ctx.source != self.instance_id:
            return
        card = ctx.game_state.get_card_instance(self.instance_id)
        if card is None or card.uses.get("ammo", 0) <= 0:
            ctx.cancel()
            ctx.game_state.log_effect("🔫 .35温彻斯特步枪：没有弹药，无法攻击")
            return
        card.uses["ammo"] -= 1
        self._attack_paid = True
        self._on_ammo_spent(ctx, 1)

    def _on_ammo_spent(self, ctx, amount: int) -> None:
        """Hook for subclasses（.45汤普森 lv3：弹药转化为资源）。"""

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def combat_bonus(self, ctx):
        """已付弹药的攻击 +2 战斗。"""
        if ctx.source != self.instance_id or not self._attack_paid:
            return
        if ctx.skill_type == Skill.COMBAT:
            ctx.modify_amount(2, "35_winchester_combat_bonus")

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.AFTER)
    def record_token(self, ctx):
        """记录本次攻击揭示的标记（供+2伤害判定）。"""
        if ctx.source != self.instance_id or not self._attack_paid:
            return
        self._revealed_token = ctx.chaos_token

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.WHEN)
    def bonus_damage(self, ctx):
        """揭示了+1/0/远古印记：本次攻击+2伤害。"""
        if ctx.source != self.instance_id or not self._attack_paid:
            return
        if ctx.skill_type != Skill.COMBAT:
            return
        if self._revealed_token in _BONUS_TOKENS:
            ctx.extra["bonus_damage"] = int(ctx.extra.get("bonus_damage", 0) or 0) + 2
            ctx.extra["35_winchester_bonus"] = True
            ctx.game_state.log_effect("🔫 .35温彻斯特步枪：揭示+1/0/远古印记，+2伤害")

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._attack_paid = False
        self._revealed_token = None
