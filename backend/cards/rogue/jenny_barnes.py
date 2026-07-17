"""Jenny Barnes — Rogue Investigator.
能力：每个补给阶段额外获得1个资源。
远古印记：+1（你每持有1个资源，+1）。

实现说明：
- 挂在 RESOURCES_GAINED 事件上，以 scenario.current_phase == Phase.UPKEEP 限定补给阶段；
  每个补给阶段只触发一次（UPKEEP_PHASE_BEGINS 重置）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import ChaosTokenType, GameEvent, Phase, TimingPriority


class JennyBarnes(CardImplementation):
    card_id = "jenny_barnes"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._given_this_upkeep = False

    def _get_jenny(self, ctx):
        """Return the investigator state iff ctx investigator is Jenny Barnes."""
        if ctx.investigator_id is None:
            return None
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return None
        card_data = getattr(inv, "card_data", None)
        if card_data is None or card_data.id != "jenny_barnes":
            return None
        return inv

    @on_event(GameEvent.UPKEEP_PHASE_BEGINS, priority=TimingPriority.WHEN)
    def reset_upkeep_limit(self, ctx):
        """补给阶段开始时重置。"""
        self._given_this_upkeep = False

    @on_event(GameEvent.RESOURCES_GAINED, priority=TimingPriority.AFTER)
    def bonus_resource_on_upkeep(self, ctx):
        """补给阶段获得资源时，额外获得1个资源。"""
        if self._given_this_upkeep:
            return
        scenario = getattr(ctx.game_state, "scenario", None)
        if scenario is None or scenario.current_phase != Phase.UPKEEP:
            return
        inv = self._get_jenny(ctx)
        if inv is None:
            return
        inv.resources += 1
        self._given_this_upkeep = True

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.WHEN)
    def elder_sign_effect(self, ctx):
        """远古印记：+1（你每持有1个资源，+1）。"""
        if ctx.chaos_token != ChaosTokenType.ELDER_SIGN:
            return
        inv = self._get_jenny(ctx)
        if inv is None:
            return
        if inv.resources > 0:
            ctx.modify_amount(inv.resources, "jenny_barnes_elder_sign")
