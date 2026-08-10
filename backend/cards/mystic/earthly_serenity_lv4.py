"""Earthly Serenity (Level 4) — Mystic Asset, Arcane slot. (08119)
使用(6充能)。[action]：检定[willpower](0)。你成功且每超过难度1点，你可以
花费1充能治愈你所在地点一位调查员1点伤害或1点恐惧。如果你成功且等于难度，
失去2资源。

简化说明：同 earthly_serenity_lv1。
"""

from backend.cards.mystic.earthly_serenity_lv1 import EarthlySerenity


class EarthlySerenityLv4(EarthlySerenity):
    card_id = "earthly_serenity_lv4"
    test_difficulty = 0
    fail_by_zero_penalty = 2
    activations = [{
        "id": "heal_test",
        "label": "意志检定(0)：每超1点花1充能治愈1伤害/恐惧",
        "method": "activate",
        "actions": 1,
    }]
