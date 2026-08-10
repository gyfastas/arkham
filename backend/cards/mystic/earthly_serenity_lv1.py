"""Earthly Serenity (Level 1) — Mystic Asset, Arcane slot. (08117)
使用(4充能)。[action]：检定[willpower](1)。你成功且每超过难度1点，你可以
花费1充能治愈你所在地点一位调查员1点伤害或1点恐惧。如果你成功且等于难度，
失去1资源。

简化说明：
- activate() 武装一次意志检定（难度由 test_difficulty 提供，会话层发起）；
  成功后按超出点数自动花费充能治疗（无逐点选择 UI）。
- 治疗目标自动选择：优先治疗你自己，先伤害后恐惧；你无恙时选你所在地点
  第一位有伤/恐的调查员（官方可自由分配——简化）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class EarthlySerenity(CardImplementation):
    card_id = "earthly_serenity_lv1"
    test_difficulty = 1       # lv4 覆盖：0
    fail_by_zero_penalty = 1  # lv4 覆盖：成功且等于难度时失去2资源
    activations = [{
        "id": "heal_test",
        "label": "意志检定(1)：每超1点花1充能治愈1伤害/恐惧",
        "method": "activate",
        "actions": 1,
    }]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._armed_by: str | None = None

    def activate(self, game_state, investigator_id: str) -> bool:
        """[action]：武装一次尘世宁静检定（由会话层发起意志检定）。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None or inst.uses.get("charges", 0) <= 0:
            return False
        self._armed_by = investigator_id
        return True

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.AFTER)
    def heal_by_margin(self, ctx):
        if self._armed_by is None or ctx.investigator_id != self._armed_by:
            return
        if ctx.skill_type != Skill.WILLPOWER:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inv is None or inst is None:
            return
        margin = max(0, (ctx.modified_skill or 0) - (ctx.difficulty or 0))
        if margin == 0:
            # 成功且等于难度：失去资源
            inv.resources = max(0, inv.resources - self.fail_by_zero_penalty)
            ctx.extra[f"{self.card_id}_resource_lost"] = self.fail_by_zero_penalty
            return
        charges = inst.uses.get("charges", 0)
        healed = 0
        for _ in range(min(margin, charges)):
            target = self._pick_heal_target(ctx, inv)
            if target is None:
                break
            inst.uses["charges"] -= 1
            if target.damage > 0:
                target.damage -= 1
                kind = "damage"
            else:
                target.horror -= 1
                kind = "horror"
            healed += 1
            ctx.extra.setdefault(f"{self.card_id}_healed", []).append(
                {"target": target.investigator_id, "kind": kind})
        if healed:
            ctx.game_state.log_effect(f"🌿 尘世宁静：花{healed}充能治愈{healed}点")

    def _pick_heal_target(self, ctx, inv):
        """治疗目标：优先自己（先伤害后恐惧），否则同地点有伤/恐的调查员。"""
        if inv.damage > 0 or inv.horror > 0:
            return inv
        for other in ctx.game_state.get_investigators_at_location(inv.location_id):
            if other.damage > 0 or other.horror > 0:
                return other
        return None

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._armed_by = None
