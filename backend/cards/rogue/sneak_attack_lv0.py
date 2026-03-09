"""Sneak Attack (Level 0) — Rogue Event.
偷袭。对你所在地点的一个疲惫敌人造成2点伤害。
"""
from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class SneakAttack(CardImplementation):
    card_id = "sneak_attack_lv0"

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def deal_damage(self, ctx):
        """Deal 2 damage to an exhausted enemy at your location."""
        if ctx.extra.get("card_id") != "sneak_attack_lv0":
            return
        target_id = ctx.extra.get("target_enemy_id")
        if not target_id:
            return
        enemy = ctx.game_state.cards_in_play.get(target_id)
        if enemy:
            enemy.damage = getattr(enemy, "damage", 0) + 2
