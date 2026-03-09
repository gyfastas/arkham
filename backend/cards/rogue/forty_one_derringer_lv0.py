""".41 Derringer (Level 0) — Rogue Asset.
.41短口手枪。使用（3弹药）。战斗：+2战斗值，成功超过2点额外+1伤害。
"""
from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class FortyOneDerringer(CardImplementation):
    card_id = "forty_one_derringer_lv0"

    # Skeleton: Uses (3 ammo), Fight +2 combat, succeed by 2+ = +1 damage
    # Requires fight sub-action with ammo tracking and succeed-by check
