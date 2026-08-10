"""Favor of the Sun (Level 1) — Neutral Asset.
快速。封印（至多3个[bless]）。若日之恩惠上没有封印的标记，丢弃之。
[reaction] 当你将从混沌袋中揭示一个混沌标记时，横置日之恩惠：
改为结算封印在此的1个标记，视同刚从混沌袋中揭示。

简化说明：与 favor_of_the_moon_lv1 相同（封印 [bless]，且无获资源效果）。
"""

from backend.cards.neutral.favor_of_the_moon_lv1 import FavorOfTheMoon
from backend.models.enums import ChaosTokenType


class FavorOfTheSun(FavorOfTheMoon):
    card_id = "favor_of_the_sun_lv1"
    token_type = ChaosTokenType.BLESS
    gain_resource = False
    activations = [{
        "id": "resolve_sealed",
        "label": "【响应】横置：改为结算封印的标记",
        "method": "activate_resolve_sealed",
    }]
