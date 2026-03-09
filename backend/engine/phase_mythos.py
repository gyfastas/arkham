"""Mythos Phase: doom, threshold check, encounter card draws."""

from __future__ import annotations

from typing import TYPE_CHECKING

from backend.models.enums import GameEvent, Phase

if TYPE_CHECKING:
    from backend.engine.event_bus import EventBus, EventContext
    from backend.models.state import GameState


class MythosPhase:
    def __init__(self, game_state: GameState, event_bus: EventBus) -> None:
        self.game_state = game_state
        self.bus = event_bus

    def resolve(self) -> None:
        """Execute the full Mythos phase (1.1-1.5)."""
        self.game_state.scenario.current_phase = Phase.MYTHOS

        # Skip mythos on round 1
        if self.game_state.scenario.round_number <= 1:
            return

        # 1.1: Phase begins
        self._emit(GameEvent.MYTHOS_PHASE_BEGINS)

        # 1.2: Place doom on agenda
        self._place_doom()

        # 1.3: Check doom threshold
        self._check_doom_threshold()

        # 1.4: Each investigator draws encounter card
        self._draw_encounter_cards()

        # 1.5: Phase ends
        self._emit(GameEvent.MYTHOS_PHASE_ENDS)

    def _place_doom(self) -> None:
        self.game_state.scenario.doom_on_agenda += 1
        self._emit(GameEvent.DOOM_PLACED, amount=1)

    def _check_doom_threshold(self) -> None:
        total = self.game_state.total_doom_in_play()
        threshold = self.game_state.scenario.effective_doom_threshold

        self._emit(GameEvent.DOOM_THRESHOLD_CHECK, amount=total)

        if total >= threshold:
            # Advance agenda
            self.game_state.scenario.doom_on_agenda = 0
            # Remove doom from all cards in play
            for card in self.game_state.cards_in_play.values():
                card.doom = 0
            for loc in self.game_state.locations.values():
                loc.doom = 0

            self.game_state.scenario.current_agenda_index += 1
            self._emit(GameEvent.AGENDA_ADVANCED)

    def _draw_encounter_cards(self) -> None:
        for inv_id in self.game_state.player_order:
            inv = self.game_state.get_investigator(inv_id)
            if inv is None:
                continue
            if not self.game_state.scenario.encounter_deck:
                continue

            card_id = self.game_state.scenario.encounter_deck.pop(0)

            self._emit(
                GameEvent.ENCOUNTER_CARD_DRAWN,
                investigator_id=inv_id,
                extra={"card_id": card_id},
            )

            # Card goes to encounter discard
            self.game_state.scenario.encounter_discard.append(card_id)

    def _emit(self, event: GameEvent, **kwargs) -> None:
        from backend.engine.event_bus import EventContext
        ctx = EventContext(
            game_state=self.game_state,
            event=event,
            **kwargs,
        )
        self.bus.emit(ctx)
