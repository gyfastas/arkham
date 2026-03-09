"""Will to Survive (Level 3) — Survivor Event.
生存意志。快速。直到回合结束，不揭示混沌标记。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class WillToSurvive(CardImplementation):
    card_id = "will_to_survive_lv3"

    # TODO: Implement fast play, suppress chaos token reveal until end of turn
