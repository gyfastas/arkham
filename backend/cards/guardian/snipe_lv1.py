"""Snipe (Level 1) — Guardian Event. (08087)
你这回合使用[[远程]]或[[枪械]]支援卡执行的下一个攻击行动中，将你抽出的每个
[skull]、[cultist]、[tablet]、[elder_thing]或[auto_fail]标记视为"0"标记。
本行动不会引起趁乱攻击。

简化说明：
- 打出后武装至回合结束；持有者下一次以远程/枪械支援发起的攻击（经
  FIGHT_ACTION_INITIATED 的武器特征判定）消耗武装。
- 坏标记"视为0"经 CHAOS_TOKEN_RESOLVED 将其修正值归零；[auto_fail] 额外经
  ctx.extra["cancel_auto_fail"] 取消自动失败（与 eucatastrophe 同通道）。
- 不引起趁乱攻击：CARD_PLAYED 先于 AoO 发出，武装一次性豁免标记。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import (
    ChaosTokenType, GameEvent, TimingPriority,
)

_BAD_TOKENS = {
    ChaosTokenType.SKULL, ChaosTokenType.CULTIST,
    ChaosTokenType.TABLET, ChaosTokenType.ELDER_THING,
    ChaosTokenType.AUTO_FAIL,
}
_WEAPON_TRAITS = ("ranged", "firearm")


class Snipe(CardImplementation):
    card_id = "snipe_lv1"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._armed_for: str | None = None
        self._active_attack = False
        self._aoo_free: str | None = None

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def arm(self, ctx):
        if ctx.extra.get("card_id") != self.card_id:
            return
        self._armed_for = ctx.investigator_id
        self._active_attack = False
        # 打出本卡的行动不引起趁乱攻击
        self._aoo_free = ctx.investigator_id

    @on_event(GameEvent.ATTACK_OF_OPPORTUNITY, priority=TimingPriority.WHEN)
    def cancel_aoo(self, ctx):
        if self._aoo_free is not None and ctx.investigator_id == self._aoo_free:
            ctx.cancel()

    @on_event(GameEvent.ACTION_PERFORMED, priority=TimingPriority.AFTER)
    def clear_aoo(self, ctx):
        self._aoo_free = None

    @on_event(GameEvent.FIGHT_ACTION_INITIATED, priority=TimingPriority.WHEN)
    def mark_attack(self, ctx):
        """仅当攻击使用远程/枪械支援时消耗武装（否则保留至下次攻击）。"""
        if self._armed_for is None or ctx.investigator_id != self._armed_for:
            return
        weapon = ctx.game_state.get_card_instance(ctx.source) if ctx.source else None
        data = ctx.game_state.get_card_data(weapon.card_id) if weapon else None
        traits = set(getattr(data, "traits", None) or [])
        if traits & set(_WEAPON_TRAITS):
            self._active_attack = True

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.WHEN)
    def zero_bad_token(self, ctx):
        """本次攻击中坏标记视为0：修正值归零，auto_fail 取消自动失败。"""
        if not self._active_attack or ctx.investigator_id != self._armed_for:
            return
        if ctx.chaos_token not in _BAD_TOKENS:
            return
        if ctx.amount:
            ctx.modify_amount(-ctx.amount, "snipe_zero_token")
        if ctx.chaos_token == ChaosTokenType.AUTO_FAIL:
            ctx.extra["cancel_auto_fail"] = True
        ctx.game_state.log_effect(
            f"🎯 狙击：【{ctx.chaos_token.value}】标记视为0")

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear_after_attack(self, ctx):
        if self._active_attack and ctx.investigator_id == self._armed_for:
            self._armed_for = None
            self._active_attack = False

    @on_event(GameEvent.INVESTIGATOR_TURN_ENDS, priority=TimingPriority.AFTER)
    def clear_at_turn_end(self, ctx):
        if ctx.investigator_id == self._armed_for:
            self._armed_for = None
            self._active_attack = False
