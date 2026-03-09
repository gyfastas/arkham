"""Guard Dog (Level 0) — Guardian Asset, Ally slot.
当敌人攻击对看门狗造成伤害时：对攻击的敌人造成1点伤害。
"""
from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class GuardDog(CardImplementation):
    card_id = "guard_dog_lv0"
    # Skeleton — DAMAGE_ASSIGNED reaction: when Guard Dog takes damage from enemy attack,
    # deal 1 damage to the attacking enemy. Needs damage-assignment event system.
