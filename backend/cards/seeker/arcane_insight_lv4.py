"""Arcane Insight (Level 4) — Seeker Asset, Arcane slot.
使用(3充能)。[快速]当一位调查员正在执行其回合时，花费1充能：
你所在地点-2隐蔽值，直到本回合结束。（每回合限一次。）

简化说明：
- 隐蔽值降低以降低智力检定难度的方式实现（与 Flashlight 同模式，
  不区分调查与其他智力检定）；
- 受益范围为在武装地点进行智力检定的任意调查员（官方为"你所在地点"，
  即所有在该地点调查的人均受益，一致）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class ArcaneInsight(CardImplementation):
    card_id = "arcane_insight_lv4"
    activations = [{
        "id": "lower_shroud",
        "label": "【快速】花1充能：本地点隐蔽-2至回合结束（每回合限1次）",
        "method": "activate",
    }]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._armed_location: str | None = None
        self._used_this_turn = False

    def activate(self, game_state, investigator_id: str) -> bool:
        """【快速】花费1充能：你所在地点隐蔽-2，直到本回合结束。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        if self._used_this_turn:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None or inst.uses.get("charges", 0) <= 0:
            return False
        inst.uses["charges"] -= 1
        self._armed_location = inv.location_id
        self._used_this_turn = True
        game_state.log_effect("🔮 奥秘洞察：本地点隐蔽值-2，直到本回合结束")
        return True

    @on_event(GameEvent.SKILL_TEST_BEGINS, priority=TimingPriority.WHEN)
    def lower_shroud(self, ctx):
        """武装地点的智力检定：难度-2。"""
        if self._armed_location is None or ctx.skill_type != Skill.INTELLECT:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or inv.location_id != self._armed_location:
            return
        if ctx.difficulty is not None and ctx.difficulty > 0:
            ctx.difficulty = max(0, ctx.difficulty - 2)
            ctx.extra["arcane_insight_lowered"] = True

    @on_event(GameEvent.INVESTIGATOR_TURN_ENDS, priority=TimingPriority.AFTER)
    def expire(self, ctx):
        """回合结束：隐蔽降低与每回合限制同时复位。"""
        self._armed_location = None
        self._used_this_turn = False
