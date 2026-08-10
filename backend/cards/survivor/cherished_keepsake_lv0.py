"""Cherished Keepsake (Level 0) — Survivor Asset, Accessory slot.
官方卡面无能力文本：自带2点理智的饰品资产（data 已有 sanity: 2）。
承恐（soak）由引擎的资产恐惧分配处理，实现故意为空效果（inert，
同 leather_coat_lv0 / elder_sign_amulet_lv3 模式）。

注意：本卡已登记入 backend/tests/test_no_inert_cards.py 的
_ALLOWED_INERT 白名单。
"""

from backend.cards.base import CardImplementation


class CherishedKeepsake(CardImplementation):
    """空效果：官方卡面无能力，承恐由引擎伤害分配处理。"""

    card_id = "cherished_keepsake_lv0"
