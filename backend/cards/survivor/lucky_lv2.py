"""Lucky! (Level 2) — Survivor Event.
Fast. Play when you would fail a skill test.
Get +2 to your skill value for that test. Draw 1 card.
（抽牌无论成败。）
"""

from backend.cards.survivor.lucky_lv0 import Lucky


class LuckyLv2(Lucky):
    card_id = "lucky_lv2"
    draw_a_card = True
