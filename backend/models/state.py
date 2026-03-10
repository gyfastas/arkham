"""Game state dataclasses for Arkham Horror LCG."""

from __future__ import annotations

import json
import warnings
from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

from backend.models.enums import CardType, Phase, PlayerClass, Skill, SlotType

if TYPE_CHECKING:
    from backend.models.investigator import InvestigatorCard


@dataclass
class SkillValues:
    willpower: int = 0
    intellect: int = 0
    combat: int = 0
    agility: int = 0

    def get(self, skill: Skill) -> int:
        if skill == Skill.WILLPOWER:
            return self.willpower
        elif skill == Skill.INTELLECT:
            return self.intellect
        elif skill == Skill.COMBAT:
            return self.combat
        elif skill == Skill.AGILITY:
            return self.agility
        return 0

    def set(self, skill: Skill, value: int) -> None:
        if skill == Skill.WILLPOWER:
            self.willpower = value
        elif skill == Skill.INTELLECT:
            self.intellect = value
        elif skill == Skill.COMBAT:
            self.combat = value
        elif skill == Skill.AGILITY:
            self.agility = value


@dataclass
class CardData:
    """Static card data loaded from JSON."""
    id: str
    name: str
    name_cn: str
    type: CardType
    card_class: PlayerClass = PlayerClass.NEUTRAL
    cost: int | None = None
    level: int = 0
    traits: list[str] = field(default_factory=list)
    skill_icons: dict[str, int] = field(default_factory=dict)
    slots: list[SlotType] = field(default_factory=list)
    text: str = ""
    health: int | None = None
    sanity: int | None = None
    keywords: list[str] = field(default_factory=list)
    unique: bool = False
    uses: dict[str, int] | None = None  # e.g. {"ammo": 4}
    fast: bool = False
    pack: str = ""

    # Investigator-specific fields
    skills: SkillValues | None = None
    ability: str = ""
    elder_sign: str = ""

    # Enemy-specific fields
    enemy_fight: int | None = None
    enemy_health: int | None = None
    enemy_evade: int | None = None
    enemy_damage: int | None = None
    enemy_horror: int | None = None

    # Location-specific fields
    shroud: int | None = None
    clue_value: int | None = None
    per_investigator: bool = False
    connections: list[str] = field(default_factory=list)


@dataclass
class CardInstance:
    """A card instance in play, with mutable state."""
    instance_id: str
    card_id: str
    owner_id: str
    controller_id: str
    exhausted: bool = False
    damage: int = 0
    horror: int = 0
    uses: dict[str, int] = field(default_factory=dict)
    attached_to: str | None = None
    slot_used: list[SlotType] = field(default_factory=list)
    doom: int = 0

    @property
    def is_ready(self) -> bool:
        return not self.exhausted


@dataclass
class InvestigatorState:
    investigator_id: str
    card_data: CardData  # Deprecated: use investigator_card instead
    location_id: str = ""
    resources: int = 5
    hand: list[str] = field(default_factory=list)          # card_id list
    deck: list[str] = field(default_factory=list)           # card_id list (top = index 0)
    discard: list[str] = field(default_factory=list)
    play_area: list[str] = field(default_factory=list)      # card instance_id list
    threat_area: list[str] = field(default_factory=list)    # enemy instance_id list
    damage: int = 0
    horror: int = 0
    clues: int = 0
    actions_remaining: int = 3
    has_taken_turn: bool = False
    # Daisy Walker extra tome action
    tome_actions_remaining: int = 0
    _investigator_card: Any = field(default=None, repr=False)

    @property
    def investigator_card(self) -> InvestigatorCard | None:
        return self._investigator_card

    @investigator_card.setter
    def investigator_card(self, value: InvestigatorCard) -> None:
        self._investigator_card = value

    @property
    def health(self) -> int:
        if self._investigator_card is not None:
            return self._investigator_card.effective_health
        return self.card_data.health or 0

    @property
    def sanity(self) -> int:
        if self._investigator_card is not None:
            return self._investigator_card.effective_sanity
        return self.card_data.sanity or 0

    @property
    def remaining_health(self) -> int:
        return max(0, self.health - self.damage)

    @property
    def remaining_sanity(self) -> int:
        return max(0, self.sanity - self.horror)

    @property
    def is_defeated(self) -> bool:
        return self.damage >= self.health or self.horror >= self.sanity

    def get_skill(self, skill: Skill) -> int:
        if self._investigator_card is not None:
            return self._investigator_card.get_skill(skill)
        if self.card_data.skills:
            return self.card_data.skills.get(skill)
        return 0


@dataclass
class LocationState:
    location_id: str
    card_data: CardData
    clues: int = 0
    enemies: list[str] = field(default_factory=list)       # unengaged enemy instance_ids
    revealed: bool = False
    doom: int = 0

    @property
    def shroud(self) -> int:
        return self.card_data.shroud or 0

    @property
    def connections(self) -> list[str]:
        return self.card_data.connections


@dataclass
class ScenarioState:
    scenario_id: str
    current_phase: Phase = Phase.SETUP
    round_number: int = 0
    doom_on_agenda: int = 0
    doom_threshold: int = 7  # Fallback if no agenda_cards defined
    act_deck: list[str] = field(default_factory=list)
    agenda_deck: list[str] = field(default_factory=list)
    current_act_index: int = 0
    current_agenda_index: int = 0
    encounter_deck: list[str] = field(default_factory=list)
    encounter_discard: list[str] = field(default_factory=list)
    victory_display: list[str] = field(default_factory=list)

    # Multi-act/agenda system (new)
    agenda_cards: dict[str, Any] = field(default_factory=dict)  # id -> AgendaCard
    act_cards: dict[str, Any] = field(default_factory=dict)     # id -> ActCard
    resolutions: dict[str, Any] = field(default_factory=dict)   # id -> Resolution

    # Scenario runtime variables (campaign log, counters, flags)
    vars: dict[str, Any] = field(default_factory=dict)

    # Scenario reference card (for chaos token values, special rules)
    scenario_card_id: str = ""

    @property
    def current_agenda(self) -> Any | None:
        """Get the current AgendaCard based on agenda_deck and current_agenda_index."""
        if not self.agenda_deck or self.current_agenda_index >= len(self.agenda_deck):
            return None
        agenda_id = self.agenda_deck[self.current_agenda_index]
        return self.agenda_cards.get(agenda_id)

    @property
    def current_act(self) -> Any | None:
        """Get the current ActCard based on act_deck and current_act_index."""
        if not self.act_deck or self.current_act_index >= len(self.act_deck):
            return None
        act_id = self.act_deck[self.current_act_index]
        return self.act_cards.get(act_id)

    @property
    def effective_doom_threshold(self) -> int:
        """Doom threshold from the current agenda card, or fallback."""
        agenda = self.current_agenda
        if agenda is not None:
            return agenda.doom_threshold
        return self.doom_threshold


@dataclass
class GameState:
    scenario: ScenarioState
    investigators: dict[str, InvestigatorState] = field(default_factory=dict)
    locations: dict[str, LocationState] = field(default_factory=dict)
    cards_in_play: dict[str, CardInstance] = field(default_factory=dict)
    card_database: dict[str, CardData] = field(default_factory=dict)
    chaos_bag: list[str] = field(default_factory=list)
    lead_investigator_id: str = ""
    player_order: list[str] = field(default_factory=list)
    _next_instance_id: int = field(default=0, repr=False)

    def next_instance_id(self) -> str:
        self._next_instance_id += 1
        return f"inst_{self._next_instance_id}"

    def get_card_data(self, card_id: str) -> CardData | None:
        return self.card_database.get(card_id)

    def get_investigator(self, investigator_id: str) -> InvestigatorState | None:
        return self.investigators.get(investigator_id)

    def get_location(self, location_id: str) -> LocationState | None:
        return self.locations.get(location_id)

    def get_card_instance(self, instance_id: str) -> CardInstance | None:
        return self.cards_in_play.get(instance_id)

    def get_engaged_enemies(self, investigator_id: str) -> list[CardInstance]:
        inv = self.investigators.get(investigator_id)
        if not inv:
            return []
        return [self.cards_in_play[eid] for eid in inv.threat_area
                if eid in self.cards_in_play]

    def get_ready_engaged_enemies(self, investigator_id: str) -> list[CardInstance]:
        return [e for e in self.get_engaged_enemies(investigator_id) if e.is_ready]

    def get_investigators_at_location(self, location_id: str) -> list[InvestigatorState]:
        return [inv for inv in self.investigators.values()
                if inv.location_id == location_id]

    def total_doom_in_play(self) -> int:
        total = self.scenario.doom_on_agenda
        for card in self.cards_in_play.values():
            total += card.doom
        for loc in self.locations.values():
            total += loc.doom
        return total
