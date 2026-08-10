"""Blinding Light (Level 0) — Mystic Event. (01066)
<b>躲避</b>。本次躲避尝试使用[willpower]代替[agility]。如果成功，对刚被躲避的敌人
造成1点伤害。如果本次躲避尝试中揭示了[skull]、[cultist]、[tablet]、[elder_thing]
或[auto_fail]标记，本回合失去1个行动。

简化说明：
- 打出后由会话层发起躲避行动；本实现通过 active_effects 武装，
  在下一次敏捷（躲避）检定中以意志代替敏捷（无额外加值）。
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


class BlindingLight(CardImplementation):
    card_id = "blinding_light_lv0"
    damage = 1            # 成功时对刚躲避的敌人造成的伤害
    horror_on_bad_token = 0  # lv2 追加1恐惧

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._bad_token_drawn = False

    def _is_armed(self, game_state, investigator_id) -> bool:
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return False
        return bool(getattr(inv, "active_effects", {}).get(self.card_id))

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def arm(self, ctx):
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if not hasattr(inv, "active_effects"):
            inv.active_effects = {}
        inv.active_effects[self.card_id] = True
        self._bad_token_drawn = False

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def substitute_willpower(self, ctx):
        """躲避检定：用意志代替敏捷（无加值）。"""
        if ctx.skill_type != Skill.AGILITY:
            return
        if not self._is_armed(ctx.game_state, ctx.investigator_id):
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        base_val = inv.get_skill(ctx.skill_type)
        willpower = inv.get_skill(Skill.WILLPOWER)
        ctx.modify_amount(willpower - base_val, f"{self.card_id}_substitute")

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.AFTER)
    def track_bad_token(self, ctx):
        if self._is_armed(ctx.game_state, ctx.investigator_id) \
                and ctx.chaos_token in _BAD_TOKENS:
            self._bad_token_drawn = True

    @on_event(GameEvent.ENEMY_EVADED, priority=TimingPriority.AFTER)
    def damage_evaded_enemy(self, ctx):
        """成功：对刚被躲避的敌人造成伤害。"""
        if not self._is_armed(ctx.game_state, ctx.investigator_id):
            return
        enemy = ctx.game_state.get_card_instance(ctx.enemy_id)
        if enemy is None:
            return
        enemy.damage += self.damage
        ctx.extra[f"{self.card_id}_damage"] = self.damage

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        armed = False
        for inv in ctx.game_state.investigators.values():
            if getattr(inv, "active_effects", {}).pop(self.card_id, None):
                armed = True
        # 坏标记惩罚：本回合失去1个行动（lv2 追加1恐惧），无论检定成败
        if armed and self._bad_token_drawn:
            inv = ctx.game_state.get_investigator(ctx.investigator_id)
            if inv is not None:
                inv.actions_remaining = max(0, inv.actions_remaining - 1)
                ctx.extra[f"{self.card_id}_action_lost"] = True
                if self.horror_on_bad_token:
                    inv.horror += self.horror_on_bad_token
                    ctx.extra[f"{self.card_id}_horror"] = self.horror_on_bad_token
        self._bad_token_drawn = False
