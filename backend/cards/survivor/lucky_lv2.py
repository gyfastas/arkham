"""Lucky! (Level 2) — Survivor Event.
快速。当你即将检定失败时，技能值+2。如果你成功，返回运气好！到你的手中。
"""

from backend.cards.survivor.lucky_lv0 import Lucky


class LuckyLv2(Lucky):
    card_id = "lucky_lv2"
    return_on_success = True
