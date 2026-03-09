"""Investigator card model — separate from player cards (CardData).

InvestigatorCard holds static investigator data + campaign state (XP, trauma).
DeckRequirement defines deck-building constraints.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.models.enums import PlayerClass, Skill
from backend.models.state import SkillValues


@dataclass
class DeckRequirement:
    """Deck-building constraints for an investigator."""
    size: int = 30
    allowed_classes: list[str] = field(default_factory=list)  # e.g. ["seeker", "neutral"]
    max_level: int = 5
    required_cards: list[str] = field(default_factory=list)   # signature card IDs
    weaknesses: list[str] = field(default_factory=list)       # weakness card IDs
    special_rules: str = ""


@dataclass
class InvestigatorCard:
    """Static investigator data + persistent campaign state.

    Unlike CardData (used for assets/events/skills/enemies/locations),
    InvestigatorCard captures investigator-specific fields:
    - Base skills (4 stats)
    - Ability / Elder Sign text
    - Deck requirements and signature cards
    - Campaign-persistent state (XP, trauma)
    """
    id: str
    name: str
    name_cn: str
    card_class: PlayerClass
    health: int
    sanity: int
    skills: SkillValues

    ability: str = ""
    elder_sign: str = ""
    traits: list[str] = field(default_factory=list)
    unique: bool = True
    pack: str = ""

    # Deck building
    deck_requirement: DeckRequirement | None = None
    signature_cards: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)

    # Campaign state (persists across scenarios)
    experience: int = 0
    physical_trauma: int = 0
    mental_trauma: int = 0

    def get_skill(self, skill: Skill) -> int:
        return self.skills.get(skill)

    @property
    def effective_health(self) -> int:
        """Health after accounting for physical trauma."""
        return max(1, self.health - self.physical_trauma)

    @property
    def effective_sanity(self) -> int:
        """Sanity after accounting for mental trauma."""
        return max(1, self.sanity - self.mental_trauma)
