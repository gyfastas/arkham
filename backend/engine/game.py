"""Main Game class — orchestrates phases, owns GameState + EventBus."""

from __future__ import annotations

from typing import TYPE_CHECKING

from backend.cards.registry import CardRegistry
from backend.engine.damage import DamageEngine
from backend.engine.event_bus import EventBus
from backend.engine.phase_enemy import EnemyPhase
from backend.engine.phase_investigation import InvestigationPhase
from backend.engine.phase_mythos import MythosPhase
from backend.engine.phase_upkeep import UpkeepPhase
from backend.engine.skill_test import SkillTestEngine
from backend.engine.slots import SlotManager
from backend.engine.actions import ActionResolver
from backend.models.chaos import ChaosBag
from backend.models.enums import GameEvent, Phase
from backend.models.state import (
    CardData, GameState, InvestigatorState, LocationState, ScenarioState,
)


class Game:
    def __init__(self, scenario_id: str = "default") -> None:
        self.state = GameState(
            scenario=ScenarioState(scenario_id=scenario_id),
        )
        self.event_bus = EventBus()
        self.chaos_bag = ChaosBag()
        self.card_registry = CardRegistry()
        self.slot_managers: dict[str, SlotManager] = {}

        # Engine components
        self.skill_test_engine = SkillTestEngine(self.state, self.event_bus, self.chaos_bag)
        self.damage_engine = DamageEngine(self.state, self.event_bus)
        self.action_resolver = ActionResolver(
            self.state, self.event_bus, self.skill_test_engine,
            self.damage_engine, self.slot_managers, self.card_registry,
        )

        # Phase objects
        self.mythos_phase = MythosPhase(self.state, self.event_bus)
        self.investigation_phase = InvestigationPhase(
            self.state, self.event_bus, self.action_resolver,
        )
        self.enemy_phase = EnemyPhase(self.state, self.event_bus, self.damage_engine)
        self.upkeep_phase = UpkeepPhase(self.state, self.event_bus)

    def register_card_data(self, card_data: CardData) -> None:
        self.state.card_database[card_data.id] = card_data

    def add_investigator(
        self,
        investigator_id: str,
        card_data: CardData,
        deck: list[str] | None = None,
        starting_location: str = "",
    ) -> InvestigatorState:
        inv = InvestigatorState(
            investigator_id=investigator_id,
            card_data=card_data,
            location_id=starting_location,
            deck=list(deck) if deck else [],
        )
        self.state.investigators[investigator_id] = inv
        self.state.player_order.append(investigator_id)
        if not self.state.lead_investigator_id:
            self.state.lead_investigator_id = investigator_id
        self.slot_managers[investigator_id] = SlotManager()
        return inv

    def add_location(
        self,
        location_id: str,
        card_data: CardData,
        clues: int = 0,
    ) -> LocationState:
        loc = LocationState(
            location_id=location_id,
            card_data=card_data,
            clues=clues,
        )
        self.state.locations[location_id] = loc
        return loc

    def setup(self) -> None:
        """Run game setup."""
        self.state.scenario.current_phase = Phase.SETUP
        self.card_registry.discover_cards()

        # Give each investigator 5 resources and draw 5 cards
        for inv_id in self.state.player_order:
            inv = self.state.get_investigator(inv_id)
            if inv:
                inv.resources = 5
                for _ in range(min(5, len(inv.deck))):
                    card_id = inv.deck.pop(0)
                    inv.hand.append(card_id)

    def run_round(self, action_callback=None, discard_callback=None) -> None:
        """Execute one full game round."""
        self.state.scenario.round_number += 1

        from backend.engine.event_bus import EventContext
        ctx = EventContext(
            game_state=self.state,
            event=GameEvent.ROUND_BEGINS,
        )
        self.event_bus.emit(ctx)

        # 1. Mythos Phase
        self.mythos_phase.resolve()

        # 2. Investigation Phase
        self.investigation_phase.resolve(action_callback)

        # 3. Enemy Phase
        self.enemy_phase.resolve()

        # 4. Upkeep Phase
        self.upkeep_phase.resolve(discard_callback)

        ctx = EventContext(
            game_state=self.state,
            event=GameEvent.ROUND_ENDS,
        )
        self.event_bus.emit(ctx)
