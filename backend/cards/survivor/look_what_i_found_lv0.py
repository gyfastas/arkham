"""\"Look what I found!\" (Level 0) — Survivor Event.
看看我发现了什么！快速。调查失败且差距不超过2时，发现2条线索。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class LookWhatIFound(CardImplementation):
    card_id = "look_what_i_found_lv0"

    # TODO: Implement fast play after failing investigate by 2 or less
    # discover 2 clues at your location
