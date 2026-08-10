"""Mists of R'lyeh (Level 0) — Mystic Asset, Arcane slot. (02230)
使用(4充能)。[action]花费1充能：躲避。本次躲避使用[willpower]代替[agility]。
如果成功，躲避所选敌人后，你可以移动到1个连接地点。如果本次躲避中揭示了
[skull]、[cultist]、[tablet]、[elder_thing]或[auto_fail]标记，选择并弃掉
你手牌中的1张牌。

简化说明：
- activate() 花费1充能并武装；随后由会话层发起躲避行动（同 blinding_light 惯例，
  不横置）。
- 成功后的移动无选择 UI：自动移动到首个连接地点；可先在
  inv.active_effects["mists_of_rlyeh_stay"]=True 选择留下（或由会话层移动）。
- 坏标记弃牌无选择 UI：自动弃掉手牌最后1张。
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


class MistsOfRlyeh(CardImplementation):
    card_id = "mists_of_rlyeh_lv0"
    willpower_bonus = 0  # lv4 覆盖：+3 意志
    activations = [{
        "id": "evade",
        "label": "花1充能：用意志躲避，成功可移动",
        "method": "activate",
        "actions": 1,
    }]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._armed = False
        self._bad_token_drawn = False

    def activate(self, game_state, investigator_id: str) -> bool:
        """花费1充能：武装一次"用意志躲避"。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None or inst.uses.get("charges", 0) <= 0:
            return False
        inst.uses["charges"] -= 1
        self._armed = True
        self._bad_token_drawn = False
        return True

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def substitute_willpower(self, ctx):
        if not self._armed or ctx.skill_type != Skill.AGILITY:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        base_val = inv.get_skill(ctx.skill_type)
        willpower = inv.get_skill(Skill.WILLPOWER)
        ctx.modify_amount(
            willpower - base_val + self.willpower_bonus,
            f"{self.card_id}_substitute",
        )

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.AFTER)
    def track_bad_token(self, ctx):
        if self._armed and ctx.chaos_token in _BAD_TOKENS:
            self._bad_token_drawn = True

    @on_event(GameEvent.ENEMY_EVADED, priority=TimingPriority.AFTER)
    def move_after_evade(self, ctx):
        """躲避成功后：移动到首个连接地点（简化：官方为可选）。"""
        if not self._armed:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if getattr(inv, "active_effects", {}).get(f"{self.card_id}_stay"):
            return
        loc = ctx.game_state.get_location(inv.location_id)
        if loc and loc.connections:
            inv.location_id = loc.connections[0]
            ctx.extra[f"{self.card_id}_moved_to"] = inv.location_id

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def cleanup(self, ctx):
        if self._armed and self._bad_token_drawn:
            inv = ctx.game_state.get_investigator(ctx.investigator_id)
            if inv is not None and inv.hand:
                discarded = inv.hand.pop()  # 简化：自动弃最后1张
                inv.discard.append(discarded)
                ctx.extra[f"{self.card_id}_discarded"] = discarded
        self._armed = False
        self._bad_token_drawn = False
