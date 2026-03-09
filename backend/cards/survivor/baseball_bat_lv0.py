"""Baseball Bat (Level 0) — Survivor Asset, 2x Hand slot.
球棒。战斗+2、伤害+1。若揭示骷髅/自动失败，攻击后弃置球棒。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class BaseballBat(CardImplementation):
    card_id = "baseball_bat_lv0"

    # TODO: Implement Fight action with +2 combat, +1 damage
    # TODO: If skull or auto_fail revealed, discard after attack
