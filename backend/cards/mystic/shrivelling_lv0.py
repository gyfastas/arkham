"""Shrivelling (Level 0) — Mystic Asset, Arcane slot. (01060)
使用(4充能)。[action]花费1充能：攻击。本次攻击使用[willpower]代替[combat]，
并造成+1伤害。如果本次攻击中揭示了[skull]、[cultist]、[tablet]、[elder_thing]
或[auto_fail]标记，受到1点恐惧。

简化说明：
- activate() 花费1充能并武装；随后由会话层发起战斗行动（weapon_instance_id
  传本卡实例），检定时以意志代替战斗（官方卡面无技能加值、无横置要求）。
- +1伤害经 ctx.extra["bonus_damage"] 通道汇入战斗结算（与 vicious_blow 等一致）。
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


class Shrivelling(CardImplementation):
    card_id = "shrivelling_lv0"
    activations = [{
        "id": "fight",
        "label": "花1充能：用意志攻击，+1伤害",
        "method": "activate",
        "actions": 1,
    }]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._armed = False

    def activate(self, game_state, investigator_id: str) -> bool:
        """花费1充能：武装一次"用意志攻击"。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None or inst.uses.get("charges", 0) <= 0:
            return False
        inst.uses["charges"] -= 1
        self._armed = True
        return True

    def _is_this_attack(self, ctx) -> bool:
        """仅当本次检定是以本卡发起的攻击（引擎经 ctx.source 传武器实例）。"""
        return self._armed and ctx.source == self.instance_id

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def substitute_willpower(self, ctx):
        if ctx.skill_type != Skill.COMBAT or not self._is_this_attack(ctx):
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        base_val = inv.get_skill(ctx.skill_type)
        willpower = inv.get_skill(Skill.WILLPOWER)
        ctx.modify_amount(willpower - base_val, "shrivelling_substitute")

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.WHEN)
    def bonus_damage(self, ctx):
        """攻击成功：+1伤害（经 bonus_damage 通道汇入战斗结算）。"""
        if not self._is_this_attack(ctx):
            return
        ctx.extra["bonus_damage"] = ctx.extra.get("bonus_damage", 0) + 1

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.AFTER)
    def horror_on_bad_token(self, ctx):
        if not self._is_this_attack(ctx) or ctx.chaos_token not in _BAD_TOKENS:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is not None:
            inv.horror += 1
            ctx.extra["shrivelling_horror"] = True

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._armed = False
