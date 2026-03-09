""".41 Derringer (Level 2) — Rogue Asset.
.41短口手枪（升级版）。使用（3弹药）。战斗：+2战斗值。成功1+额外+1伤害，成功3+获得额外行动。
"""
from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class FortyOneDerringerLv2(CardImplementation):
    card_id = "forty_one_derringer_lv2"

    # Skeleton: Uses (3 ammo). Fight +2 combat.
    # Succeed by 1+ = +1 damage. Succeed by 3+ = take additional action.
    # Requires fight sub-action with ammo tracking and succeed-by checks
