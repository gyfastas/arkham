"""Trench Coat (Level 0) — Neutral Asset, Body slot.
你在躲避尝试中+1敏捷。

简化说明：
- "躲避尝试"以 EVADE_ACTION_INITIATED / SKILL_TEST_ENDS 圈定（引擎的躲避
  检定不带来源标记，同 trench_knife_lv0 的行动标记法）；只有本卡持有者的
  躲避获得加值。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class TrenchCoat(CardImplementation):
    card_id = "trench_coat_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._evading = False

    @on_event(GameEvent.EVADE_ACTION_INITIATED, priority=TimingPriority.WHEN)
    def mark_evasion(self, ctx):
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is not None and self.instance_id in inv.play_area:
            self._evading = True

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def agility_bonus(self, ctx):
        """躲避尝试中 +1敏捷。"""
        if not self._evading or ctx.skill_type != Skill.AGILITY:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        ctx.modify_amount(1, "trench_coat_agility_bonus")

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._evading = False
