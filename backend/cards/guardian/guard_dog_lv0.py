"""Guard Dog (Level 0) — Guardian Asset, Ally slot.
强制 - 在你受到敌人伤害后：对攻击者造成1点伤害。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class GuardDog(CardImplementation):
    card_id = "guard_dog_lv0"

    @on_event(GameEvent.DAMAGE_DEALT, priority=TimingPriority.AFTER)
    def retaliate(self, ctx):
        """你受到敌人伤害后：对攻击者造成1点伤害。"""
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        if (ctx.amount or 0) < 1:
            return
        attacker_id = ctx.source
        if not attacker_id:
            return
        attacker = ctx.game_state.get_card_instance(attacker_id)
        if attacker is None:
            return
        attacker_data = ctx.game_state.get_card_data(attacker.card_id)
        from backend.models.enums import CardType
        if attacker_data is None or attacker_data.type != CardType.ENEMY:
            return
        attacker.damage += 1
        ctx.extra["guard_dog_retaliate"] = attacker_id
        ctx.game_state.log_effect("🐕 看门狗：对攻击者造成1点伤害")
