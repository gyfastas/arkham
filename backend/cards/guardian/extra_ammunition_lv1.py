"""Extra Ammunition (Level 1) — Guardian Event.
在一个火器资产上放置3发弹药。
"""
from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class ExtraAmmunition(CardImplementation):
    card_id = "extra_ammunition_lv1"
    # Skeleton — requires asset targeting to place ammo on a Firearm.
