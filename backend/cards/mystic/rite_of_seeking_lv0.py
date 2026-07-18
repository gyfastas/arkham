"""Rite of Seeking (Level 0) — Mystic Asset, Arcane slot.
使用(3充能)。[action]花费1充能：调查。这次调查不使用[intellect]，改为使用[willpower]。
如果成功，额外发现所在地点1个线索。如果检定中抽出[skull]、[cultist]、[tablet]、
[elder_thing]或[auto_fail]标记，在检定结束后，失去所有剩余行动，并立刻结束你的回合。

简化说明：
- activate() 花费1充能并武装；随后由会话层发起调查行动，
  本实现在检定时替换智力为意志。
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


class RiteOfSeeking(CardImplementation):
    card_id = "rite_of_seeking_lv0"
    extra_clue = True
    bad_token_penalty = True

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._armed = False
        self._bad_token_drawn = False

    def activate(self, game_state, investigator_id: str) -> bool:
        """花费1充能：武装一次"用意志调查"。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None or inst.uses.get("charges", 0) <= 0:
            return False
        inst.uses["charges"] -= 1
        inst.exhausted = True
        self._armed = True
        self._bad_token_drawn = False
        return True

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def substitute_willpower(self, ctx):
        if not self._armed or ctx.skill_type != Skill.INTELLECT:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        willpower = inv.get_skill(Skill.WILLPOWER)
        ctx.modify_amount(willpower - ctx.amount, f"{self.card_id}_substitute")

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.AFTER)
    def track_bad_token(self, ctx):
        if self._armed and ctx.chaos_token in _BAD_TOKENS:
            self._bad_token_drawn = True

    @on_event(GameEvent.CLUE_DISCOVERED, priority=TimingPriority.AFTER)
    def bonus_clue(self, ctx):
        """成功：额外发现1个线索。"""
        if not self._armed or not self.extra_clue:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        loc = ctx.game_state.get_location(ctx.location_id or inv.location_id)
        if loc is not None and loc.clues > 0:
            loc.clues -= 1
            inv.clues += 1
            ctx.extra[f"{self.card_id}_extra_clue"] = True

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def cleanup(self, ctx):
        if self._armed and self._bad_token_drawn and self.bad_token_penalty:
            inv = ctx.game_state.get_investigator(ctx.investigator_id)
            if inv is not None:
                inv.actions_remaining = 0
                ctx.extra[f"{self.card_id}_turn_ended"] = True
        self._armed = False
        self._bad_token_drawn = False
