"""Crafty (Level 3) — Seeker Asset. (08123)
使用(2资源)。每轮开始时补充这些资源。
巧手上的资源可用于支付[[洞察]]、[[工具]]或[[诡计]]卡牌。
[快速]在一张[[洞察]]、[[工具]]或[[诡计]]卡牌的技能检定中，花费巧手上
1资源：本次检定你获得+1技能值。

实现：与 antiquary_lv3 共用同一引擎（仅特性集合与卡面不同）。
简化说明与引擎缺口（跨卡支付通道）见 antiquary_lv3.py。
"""

from backend.cards.seeker.antiquary_lv3 import Antiquary


class Crafty(Antiquary):
    card_id = "crafty_lv3"
    paid_traits = ("insight", "tool", "trick")
