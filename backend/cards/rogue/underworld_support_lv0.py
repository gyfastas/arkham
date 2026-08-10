"""Underworld Support (Level 0) — Rogue Asset. (08046)
永久。每副牌组限制1张。当牌组构建时购买。
你的牌组中每张非弱点、非专属卡牌最多只能有一张同名卡牌。
你的牌组卡牌张数减5。

简化说明：
- 永久卡：不进牌局，无场内效果；牌组构建规则以纯函数形式提供
  （validate_deck / deck_size_adjustment），供牌组校验层调用
  （引擎当前无牌组校验入口——引擎缺口）。
- 专属卡判定：卡面含 "deck only." 文本（如 "Roland's .38 Special deck only."）。
"""

from backend.cards.base import CardImplementation
from backend.models.state import is_weakness_card


class UnderworldSupport(CardImplementation):
    card_id = "underworld_support_lv0"

    @staticmethod
    def deck_size_adjustment() -> int:
        """牌组卡牌张数减5（如30张牌组变为25张）。"""
        return -5

    @staticmethod
    def validate_deck(card_ids, card_database) -> list[str]:
        """校验牌组满足"每张非弱点、非专属卡最多1张（按标题）"。

        返回违反规则的卡标题列表（重复一次记一条）；空列表表示合法。
        """
        counts: dict[str, int] = {}
        for card_id in card_ids:
            if card_id == UnderworldSupport.card_id:
                continue
            cd = card_database.get(card_id)
            if cd is None:
                continue
            if is_weakness_card(cd):
                continue
            if "deck only." in (cd.text or ""):
                continue  # 专属卡不受限
            title = cd.name or card_id
            counts[title] = counts.get(title, 0) + 1
        return sorted(title for title, n in counts.items() if n > 1)
