"""Michael Leigh (Level 5) — Guardian Asset, Ally slot. (08086)
你获得+1[智力]和+1[战斗]。
[反应] 在你成功调查后：在迈克尔·利上放置1个资源（来自供应堆），
作为证据（至多3个证据）。
[反应] 当你发起攻击时，横置迈克尔·利并花费1个证据：本次攻击你造成+1伤害。

简化说明：
- "成功调查"按 dr_milan 模式跟踪：INVESTIGATE_ACTION_INITIATED 记录调查者，
  随后的 SKILL_TEST_SUCCESSFUL（智力）即成功调查；证据存于实例
  uses["evidence"]（至多3）。
- [反应]加伤为玩家选择时机，实现为公开方法 activate_damage()（横置+花1证据，
  武装持有者下一次战斗检定+1伤害），经 activations 暴露给 UI。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority

_MAX_EVIDENCE = 3


class MichaelLeigh(CardImplementation):
    card_id = "michael_leigh_lv5"
    activations = [{
        "id": "spend_evidence",
        "label": "【响应】横置+1证据：本次攻击+1伤害",
        "method": "activate_damage",
        "actions": 0,
    }]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._investigating: str | None = None
        self._damage_armed_for: str | None = None

    # ---- 常驻加值 ----
    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def skill_bonus(self, ctx):
        """+1 智力、+1 战斗（在场时）。"""
        if ctx.skill_type not in (Skill.INTELLECT, Skill.COMBAT):
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is not None and self.instance_id in inv.play_area:
            ctx.modify_amount(1, "michael_leigh_bonus")

    # ---- 证据积累 ----
    @on_event(GameEvent.INVESTIGATE_ACTION_INITIATED, priority=TimingPriority.AFTER)
    def track_investigate(self, ctx):
        self._investigating = ctx.investigator_id

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.REACTION)
    def gain_evidence(self, ctx):
        """你成功调查后：放置1个证据（至多3）。"""
        if ctx.skill_type != Skill.INTELLECT:
            return
        if self._investigating != ctx.investigator_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inv is None or inst is None or self.instance_id not in inv.play_area:
            return
        evidence = inst.uses.get("evidence", 0)
        if evidence >= _MAX_EVIDENCE:
            return
        inst.uses["evidence"] = evidence + 1
        ctx.extra["michael_leigh_evidence"] = evidence + 1
        ctx.game_state.log_effect(
            f"🕵️ 迈克尔·利：放置1个证据（现有{evidence + 1}个）")

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear_tracking(self, ctx):
        self._investigating = None

    # ---- 证据消费 ----
    def activate_damage(self, game_state, investigator_id: str) -> bool:
        """[反应] 发起攻击时：横置+花1证据，本次攻击+1伤害。"""
        inv = game_state.get_investigator(investigator_id)
        inst = game_state.get_card_instance(self.instance_id)
        if inv is None or inst is None or self.instance_id not in inv.play_area:
            return False
        if inst.exhausted or inst.uses.get("evidence", 0) <= 0:
            return False
        inst.exhausted = True
        inst.uses["evidence"] -= 1
        self._damage_armed_for = investigator_id
        game_state.log_effect("🕵️ 迈克尔·利：横置并花费1证据，本次攻击+1伤害")
        return True

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.WHEN)
    def bonus_damage(self, ctx):
        """武装的攻击成功：+1伤害。"""
        if self._damage_armed_for is None:
            return
        if ctx.investigator_id != self._damage_armed_for:
            return
        if ctx.skill_type != Skill.COMBAT:
            return
        ctx.extra["bonus_damage"] = int(ctx.extra.get("bonus_damage", 0) or 0) + 1
        ctx.extra["michael_leigh_bonus_damage"] = True

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear_damage(self, ctx):
        self._damage_armed_for = None
