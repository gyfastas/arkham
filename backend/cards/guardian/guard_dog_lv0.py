"""Guard Dog (Level 0) — Guardian Asset, Ally slot.
[反应] 当敌人攻击对看门狗造成伤害后：对攻击的敌人造成1点伤害。

实现说明：
- 引擎对调查员/盟友受伤发 DAMAGE_ASSIGNED（DAMAGE_DEALT 仅用于敌人），
  且盟友分担在事件发出前已结算，ctx 不含分担目标。因此本卡在
  ENEMY_ATTACKS / ATTACK_OF_OPPORTUNITY 时快照看门狗当前伤害，
  在随后的 DAMAGE_ASSIGNED 中比较增量，确认伤害确实分给了看门狗再反击。
- 遗留简化：若这次攻击直接击败看门狗（离场后无法比较增量），不反击。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import CardType, GameEvent, TimingPriority


class GuardDog(CardImplementation):
    card_id = "guard_dog_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        # (攻击者 instance_id, 攻击前看门狗已受伤害)
        self._attack_snapshot: tuple[str | None, int] | None = None

    def _dog_in_play(self, ctx):
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return None, None
        dog = ctx.game_state.get_card_instance(self.instance_id)
        return inv, dog

    @on_event(GameEvent.ENEMY_ATTACKS, priority=TimingPriority.WHEN)
    @on_event(GameEvent.ATTACK_OF_OPPORTUNITY, priority=TimingPriority.WHEN)
    def snapshot_on_attack(self, ctx):
        """敌人攻击时：记录看门狗当前伤害，供随后反击判定。"""
        inv, dog = self._dog_in_play(ctx)
        if dog is None:
            return
        self._attack_snapshot = (ctx.enemy_id or ctx.source, dog.damage)

    @on_event(GameEvent.DAMAGE_ASSIGNED, priority=TimingPriority.AFTER)
    def retaliate(self, ctx):
        """敌人攻击对看门狗造成伤害后：对攻击者造成1点伤害。"""
        if self._attack_snapshot is None:
            return
        attacker_id, damage_before = self._attack_snapshot
        self._attack_snapshot = None

        inv, dog = self._dog_in_play(ctx)
        if dog is None:
            return
        if dog.damage <= damage_before:
            return  # 伤害没有分给看门狗

        attacker_id = ctx.source or attacker_id
        attacker = (
            ctx.game_state.get_card_instance(attacker_id) if attacker_id else None
        )
        if attacker is None:
            return
        attacker_data = ctx.game_state.get_card_data(attacker.card_id)
        if attacker_data is None or attacker_data.type != CardType.ENEMY:
            return
        attacker.damage += 1
        ctx.extra["guard_dog_retaliate"] = attacker_id
        ctx.game_state.log_effect("🐕 看门狗：对攻击者造成1点伤害")
