"""Sleuth (Level 3) — Guardian Asset. (08121)
使用(2资源)。当每轮开始时重新补满这些资源。
一探究竟上的资源可以被用来支付[[守护]]、[[策略]]或[[书籍]]卡牌。
[fast]在[[守护]]、[[策略]]或[[书籍]]卡牌上的技能检定中，从一探究竟花费1资源：
你这次检定+1技能值。

实现与 prophetic_lv3 共享基类（特征不同：Charm/Tactic/Tome）。
"""

from backend.cards.guardian.prophetic_lv3 import TraitResourceTalent


class Sleuth(TraitResourceTalent):
    card_id = "sleuth_lv3"
    payable_traits = ("charm", "tactic", "tome")
