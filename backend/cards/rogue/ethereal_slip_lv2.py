"""Ethereal Slip (Level 2) — Rogue Event. (08110)
选择任何已揭示地点的一名非[[精英]]敌人。与该敌人交换位置。

简化说明：同 ethereal_slip_lv0，仅范围改为任意已揭示地点（不限距离）。
"""

from backend.cards.rogue.ethereal_slip_lv0 import EtherealSlip


class EtherealSlipLv2(EtherealSlip):
    card_id = "ethereal_slip_lv2"
    max_distance = None  # 任意已揭示地点
