"""Unearth the Ancients (Level 2) — Seeker Event. (08039)
调查。选择你手中最多2张[seeker]支援卡。这次技能检定难度等于所选支援
卡费用之和。如果你成功，将所选支援卡依次放置入场。每有1张[[遗物]]
支援卡通过此能力放置入场，抽1张牌。

简化说明：同 unearth_the_ancients_lv0（CardSelfTest 回放检定、自动选择
费用最高的前2张、放置入场不付所选卡费用、入场实现注册为引擎缺口）。
"""

from backend.cards.seeker.unearth_the_ancients_lv0 import UnearthTheAncients


class UnearthTheAncientsLv2(UnearthTheAncients):
    card_id = "unearth_the_ancients_lv2"
    max_assets = 2
