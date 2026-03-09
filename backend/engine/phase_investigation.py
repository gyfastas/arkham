"""Investigation Phase: investigator turns with 3 actions each."""

from __future__ import annotations

from typing import TYPE_CHECKING

from backend.models.enums import GameEvent, Phase

if TYPE_CHECKING:
    from backend.engine.actions import ActionResolver
    from backend.engine.event_bus import EventBus, EventContext
    from backend.models.state import GameState


class InvestigationPhase:
    def __init__(
        self,
        game_state: GameState,
        event_bus: EventBus,
        action_resolver: ActionResolver,
    ) -> None:
        self.game_state = game_state
        self.bus = event_bus
        self.actions = action_resolver

    def resolve(self, action_callback=None) -> None:
        """Execute the Investigation phase (2.1-2.3).

        action_callback: A function that takes (investigator_id, actions_remaining, action_resolver)
                        and returns the next action to perform, or None to end turn.
                        If None, investigators take no actions (for testing).
        """
        self.game_state.scenario.current_phase = Phase.INVESTIGATION

        # 2.1: Phase begins
        self._emit(GameEvent.INVESTIGATION_PHASE_BEGINS)

        # 2.2: Each investigator takes a turn
        for inv_id in self.game_state.player_order:
            inv = self.game_state.get_investigator(inv_id)
            if inv is None:
                continue

            inv.actions_remaining = 3
            inv.has_taken_turn = False

            self._emit(GameEvent.INVESTIGATOR_TURN_BEGINS, investigator_id=inv_id)

            # Player takes actions until 0 remaining or chooses to end
            if action_callback:
                while inv.actions_remaining > 0:
                    action_spec = action_callback(inv_id, inv.actions_remaining, self.actions)
                    if action_spec is None:
                        break
                    action, kwargs = action_spec
                    self.actions.perform_action(inv_id, action, **kwargs)

            inv.has_taken_turn = True
            self._emit(GameEvent.INVESTIGATOR_TURN_ENDS, investigator_id=inv_id)

        # 2.3: Phase ends
        self._emit(GameEvent.INVESTIGATION_PHASE_ENDS)

    def _emit(self, event: GameEvent, **kwargs) -> None:
        from backend.engine.event_bus import EventContext
        ctx = EventContext(
            game_state=self.game_state,
            event=event,
            **kwargs,
        )
        self.bus.emit(ctx)
