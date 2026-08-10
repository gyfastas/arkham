"""The Red Clock (Level 5) — Rogue Asset. (08058)
卓越。使用(0充能)。
强制 - 在你的回合开始后：你可以取走此处所有充能作为资源。在此放置1充能。
如果其正好有……
- 1充能：下次技能检定你+4技能值。
- 2充能：你可以移动最多3次。
- 3充能：这回合你可以进行2个额外行动。

简化说明：
- 与 lv2 的差异：取走充能后仍放置1充能（always_place），自动决策为
  充能≥3时先取走作为资源再放置（随后落在1充能拿+4）。其余同 lv2，
  见 the_red_clock_lv2.py 注释。
"""

from backend.cards.rogue.the_red_clock_lv2 import TheRedClockLv2


class TheRedClockLv5(TheRedClockLv2):
    card_id = "the_red_clock_lv5"
    skill_bonus = 4
    free_moves = 3
    bonus_actions = 2
    take_threshold = 3
    always_place = True
