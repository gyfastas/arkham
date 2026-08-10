"""No Stone Unturned (Level 5) — Seeker Event, Fast.
快速。可在任意[快速]玩家窗口打出。
选择你所在地点的1位调查员。该调查员检索其牌库中的1张牌，
抽取之，并洗混其牌库。

简化说明：同 lv0（见 no_stone_unturned_lv0），检索范围为整个牌库。
"""

from backend.cards.seeker.no_stone_unturned_lv0 import NoStoneUnturned


class NoStoneUnturnedLv5(NoStoneUnturned):
    card_id = "no_stone_unturned_lv5"
    search_depth = 0  # 0 = 整个牌库
