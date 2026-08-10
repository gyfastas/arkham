"""Leather Coat (Level 0) — Survivor Asset, Body slot.
官方卡面无能力文本：2点生命的护甲资产。
soak（伤害吸收）由引擎的资产伤害分配处理（data 已有 health: 2），
实现故意为空效果（inert）。

注意：本卡应加入 backend/tests/test_no_inert_cards.py 的 _ALLOWED_INERT
白名单（该文件不在本阵营修改权限内，已在修复报告中登记）。
"""

from backend.cards.base import CardImplementation


class LeatherCoat(CardImplementation):
    """空效果：官方卡面无能力，soak 由引擎伤害分配处理。"""

    card_id = "leather_coat_lv0"
