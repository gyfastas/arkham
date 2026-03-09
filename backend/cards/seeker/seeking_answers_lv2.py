"""Seeking Answers (Level 2) — Seeker Event.
调查。成功时发现所在地点和连接地点共计2条线索。
"""

from backend.cards.base import CardImplementation


class SeekingAnswersLv2(CardImplementation):
    card_id = "seeking_answers_lv2"
    # Skeleton — upgraded version of Seeking Answers lv0
    # Discovers 2 clues split across location and connected locations
