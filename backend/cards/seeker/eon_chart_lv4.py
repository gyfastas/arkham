"""Eon Chart (Level 4) — Seeker Asset, Accessory slot. (08100)
使用(3秘密)。
[快速]在你的回合中，横置万古图表并花费1秘密：选择并按任意顺序执行以下
行动中的两项不同行动（移动、躲避或调查）。

实现：与 eon_chart_lv1 共用同一引擎（activate(actions=[...]) 传两项不同
行动）。简化说明见 eon_chart_lv1.py。
"""

from backend.cards.seeker.eon_chart_lv1 import EonChart


class EonChartLv4(EonChart):
    card_id = "eon_chart_lv4"
    actions_per_use = 2
    activations = [{
        "id": "extra_actions",
        "label": "[快速]横置+1秘密：执行移动/躲避/调查中的两项不同行动",
        "method": "activate",
    }]
