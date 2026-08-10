"""Alchemical Transmutation (Level 0) — Mystic Asset, Arcane slot. (03032)
使用(3充能)。[action] 横置炼金转化并花费1充能：检定[willpower](1)。
你成功时每超过难度1点，获得1个资源（至多3个）。如果本次检定中揭示了
[skull]、[cultist]、[tablet]、[elder_thing]或[auto_fail]标记，受到1点伤害。

简化说明：
- activate() 横置并花费1充能后武装；随后的下一次意志检定结算资源获取
  （由会话层/客户端发起难度1的意志检定，与 rite_of_seeking/blinding_light
  的"武装+外部发起检定"模式一致）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import (
    ChaosTokenType, GameEvent, Skill, TimingPriority,
)

_BAD_TOKENS = {
    ChaosTokenType.SKULL, ChaosTokenType.CULTIST,
    ChaosTokenType.TABLET, ChaosTokenType.ELDER_THING,
    ChaosTokenType.AUTO_FAIL,
}


class AlchemicalTransmutation(CardImplementation):
    card_id = "alchemical_transmutation_lv0"
    activations = [{
        "id": "transmute",
        "label": "横置+1充能：意志检定(1)，每超1点得1资源（至多3）",
        "method": "activate",
        "actions": 1,
    }]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._armed_by: str | None = None

    def activate(self, game_state, investigator_id: str) -> bool:
        """横置并花费1充能：武装一次炼金转化检定。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None or inst.exhausted or inst.uses.get("charges", 0) <= 0:
            return False
        inst.uses["charges"] -= 1
        inst.exhausted = True
        self._armed_by = investigator_id
        return True

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.AFTER)
    def gain_resources(self, ctx):
        """成功：每超过难度1点获得1资源（至多3）。"""
        if self._armed_by is None or ctx.investigator_id != self._armed_by:
            return
        if ctx.skill_type != Skill.WILLPOWER:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        margin = max(0, (ctx.modified_skill or 0) - (ctx.difficulty or 0))
        gained = min(3, margin)
        if gained > 0:
            inv.resources += gained
            ctx.extra["alchemical_transmutation_resources"] = gained
            ctx.game_state.log_effect(
                f"⚗️ 炼金转化：超过难度{margin}点，获得{gained}资源")

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.AFTER)
    def damage_on_bad_token(self, ctx):
        """检定中揭示坏标记：受到1点伤害。"""
        if self._armed_by is None or ctx.investigator_id != self._armed_by:
            return
        if ctx.chaos_token not in _BAD_TOKENS:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is not None:
            inv.damage += 1
            ctx.extra["alchemical_transmutation_damage"] = True

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._armed_by = None
