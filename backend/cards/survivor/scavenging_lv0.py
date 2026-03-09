"""Scavenging (Level 0) — Survivor Asset.
拾荒。调查成功超出2+时，疲倦此卡：从弃牌堆回收一张道具卡。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class Scavenging(CardImplementation):
    card_id = "scavenging_lv0"

    # TODO: Implement SKILL_TEST_SUCCESSFUL reaction for investigate by 2+
    # exhaust self, return Item from discard to hand
