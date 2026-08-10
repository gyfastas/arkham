"""Eye of Chaos (Level 4) — Mystic Asset, Arcane slot.
使用(3充能)。[action]花费1充能：调查。本次调查使用[willpower]代替[intellect]，
且本次检定+2[willpower]。如果成功，额外发现所在地点1个线索。本次调查中每揭示
1个[curse]标记，你可以发现1个连接地点的1个线索，或在混沌之眼上放置1充能。

简化说明：同 lv0（[curse]奖励自动优先取连接地点线索，否则放充能）；
lv4 按每个[curse]标记各结算一次。
"""

from backend.cards.mystic.eye_of_chaos_lv0 import EyeOfChaos


class EyeOfChaosLv4(EyeOfChaos):
    card_id = "eye_of_chaos_lv4"
    willpower_bonus = 2
    per_curse_token = True
