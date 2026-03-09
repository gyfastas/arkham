"""Multi-act/agenda scenario model with branching conditions.

Supports:
- Multiple agenda cards with per-card doom thresholds
- Multiple act cards with clue/condition-based advancement
- Advance effects (spawn enemies, add locations, deal damage, etc.)
- Branching on advancement (condition-based target selection)
- Scenario resolutions (ending variants)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class AdvanceEffectType(Enum):
    """Types of effects triggered when an act/agenda advances."""
    SPAWN_ENEMY = "spawn_enemy"
    ADD_LOCATION = "add_location"
    REMOVE_LOCATION = "remove_location"
    ADD_DOOM = "add_doom"
    REMOVE_DOOM = "remove_doom"
    DEAL_DAMAGE = "deal_damage"
    DEAL_HORROR = "deal_horror"
    HEAL_DAMAGE = "heal_damage"
    HEAL_HORROR = "heal_horror"
    GAIN_CLUES = "gain_clues"
    LOSE_CLUES = "lose_clues"
    GAIN_RESOURCES = "gain_resources"
    SHUFFLE_ENCOUNTER = "shuffle_encounter"
    ADD_TO_ENCOUNTER = "add_to_encounter"
    BRANCH = "branch"
    RESOLUTION = "resolution"
    CUSTOM = "custom"


@dataclass
class AdvanceEffect:
    """A single effect triggered when an act/agenda advances."""
    type: AdvanceEffectType
    params: dict = field(default_factory=dict)
    # params examples:
    # SPAWN_ENEMY: {"enemy_id": "ghoul", "location": "hallway"}
    # DEAL_DAMAGE: {"amount": 2, "target": "all_investigators"}
    # BRANCH: {"condition": "clues >= 5", "true_target": "act_2a", "false_target": "act_2b"}
    # RESOLUTION: {"resolution_id": "R1"}


@dataclass
class Branch:
    """Conditional branching when an act/agenda advances."""
    condition: str  # Evaluable condition string, e.g. "clues >= 5", "has_card:key"
    true_target: str   # Target act/agenda ID if condition is true
    false_target: str  # Target act/agenda ID if condition is false
    description: str = ""
    description_cn: str = ""


@dataclass
class AgendaCard:
    """A single agenda card in the agenda deck.

    Agenda advances when total doom in play >= doom_threshold.
    """
    id: str
    name: str
    name_cn: str
    doom_threshold: int
    sequence: int = 1  # Position in agenda deck (1-based)
    text: str = ""
    text_cn: str = ""
    back_text: str = ""    # Flavor/effect text when flipped
    back_text_cn: str = ""
    advance_effects: list[AdvanceEffect] = field(default_factory=list)
    branch: Branch | None = None  # If advancing has branching


@dataclass
class ActCard:
    """A single act card in the act deck.

    Act advances when players spend clue_threshold clues (or meet special condition).
    """
    id: str
    name: str
    name_cn: str
    sequence: int = 1  # Position in act deck (1-based)
    clue_threshold: int | None = None  # Clues needed to advance (None = special condition)
    text: str = ""
    text_cn: str = ""
    back_text: str = ""
    back_text_cn: str = ""
    advance_condition: str = ""  # Description of special advance condition
    advance_effects: list[AdvanceEffect] = field(default_factory=list)
    branch: Branch | None = None


@dataclass
class Resolution:
    """A scenario resolution (ending variant)."""
    id: str
    name: str
    name_cn: str
    text: str = ""
    text_cn: str = ""
    effects: list[AdvanceEffect] = field(default_factory=list)
    # Campaign effects
    xp_reward: int = 0
    trauma_damage: int = 0
    trauma_horror: int = 0
