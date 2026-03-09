"""All game enumerations for Arkham Horror LCG."""

from enum import Enum, auto


class Phase(Enum):
    SETUP = auto()
    MYTHOS = auto()
    INVESTIGATION = auto()
    ENEMY = auto()
    UPKEEP = auto()


class Action(Enum):
    INVESTIGATE = auto()
    MOVE = auto()
    DRAW = auto()
    RESOURCE = auto()
    FIGHT = auto()
    ENGAGE = auto()
    EVADE = auto()
    PLAY = auto()
    ACTIVATE = auto()
    PARLEY = auto()
    RESIGN = auto()


# Actions that do NOT provoke attacks of opportunity
AOO_EXEMPT_ACTIONS = {Action.FIGHT, Action.EVADE, Action.PARLEY, Action.RESIGN}


class Skill(Enum):
    WILLPOWER = "willpower"
    INTELLECT = "intellect"
    COMBAT = "combat"
    AGILITY = "agility"
    WILD = "wild"


class SlotType(Enum):
    HAND = "hand"
    ARCANE = "arcane"
    ACCESSORY = "accessory"
    BODY = "body"
    ALLY = "ally"
    TAROT = "tarot"


# Max slots per investigator
SLOT_LIMITS = {
    SlotType.HAND: 2,
    SlotType.ARCANE: 2,
    SlotType.ACCESSORY: 1,
    SlotType.BODY: 1,
    SlotType.ALLY: 1,
    SlotType.TAROT: 1,
}


class CardType(Enum):
    ASSET = "asset"
    EVENT = "event"
    SKILL = "skill"
    ENEMY = "enemy"
    TREACHERY = "treachery"
    LOCATION = "location"
    INVESTIGATOR = "investigator"


class PlayerClass(Enum):
    GUARDIAN = "guardian"
    SEEKER = "seeker"
    ROGUE = "rogue"
    MYSTIC = "mystic"
    SURVIVOR = "survivor"
    NEUTRAL = "neutral"


class GameEvent(Enum):
    # Phase boundaries
    ROUND_BEGINS = auto()
    ROUND_ENDS = auto()
    MYTHOS_PHASE_BEGINS = auto()
    MYTHOS_PHASE_ENDS = auto()
    INVESTIGATION_PHASE_BEGINS = auto()
    INVESTIGATION_PHASE_ENDS = auto()
    ENEMY_PHASE_BEGINS = auto()
    ENEMY_PHASE_ENDS = auto()
    UPKEEP_PHASE_BEGINS = auto()
    UPKEEP_PHASE_ENDS = auto()

    # Mythos framework
    DOOM_PLACED = auto()
    DOOM_THRESHOLD_CHECK = auto()
    AGENDA_ADVANCED = auto()
    ENCOUNTER_CARD_DRAWN = auto()

    # Investigation framework
    INVESTIGATOR_TURN_BEGINS = auto()
    INVESTIGATOR_TURN_ENDS = auto()
    ACTION_PERFORMED = auto()

    # Skill test (ST.1 - ST.8)
    SKILL_TEST_BEGINS = auto()
    SKILL_TEST_COMMIT = auto()
    CHAOS_TOKEN_REVEALED = auto()
    CHAOS_TOKEN_RESOLVED = auto()
    SKILL_VALUE_DETERMINED = auto()
    SKILL_TEST_SUCCESSFUL = auto()
    SKILL_TEST_FAILED = auto()
    SKILL_TEST_APPLY_RESULTS = auto()
    SKILL_TEST_ENDS = auto()

    # Actions
    FIGHT_ACTION_INITIATED = auto()
    INVESTIGATE_ACTION_INITIATED = auto()
    EVADE_ACTION_INITIATED = auto()
    MOVE_ACTION_INITIATED = auto()
    PLAY_ACTION_INITIATED = auto()

    # Damage / Horror
    DAMAGE_DEALT = auto()
    HORROR_DEALT = auto()
    DAMAGE_ASSIGNED = auto()
    HORROR_ASSIGNED = auto()

    # Card lifecycle
    CARD_PLAYED = auto()
    CARD_ENTERS_PLAY = auto()
    CARD_LEAVES_PLAY = auto()
    CARD_EXHAUSTED = auto()
    CARD_READIED = auto()
    CARD_DRAWN = auto()
    CARD_DISCARDED = auto()

    # Combat
    ATTACK_OF_OPPORTUNITY = auto()
    ENEMY_ATTACKS = auto()
    ENEMY_ENGAGED = auto()
    ENEMY_DISENGAGED = auto()
    ENEMY_DEFEATED = auto()
    ENEMY_EVADED = auto()

    # Clues
    CLUE_DISCOVERED = auto()

    # Defeat
    INVESTIGATOR_DEFEATED = auto()
    ASSET_DEFEATED = auto()

    # Resources
    RESOURCES_GAINED = auto()
    RESOURCES_SPENT = auto()


class TimingPriority(Enum):
    """Handler execution order within a game event."""
    WHEN = 0       # "When..." interrupts
    FORCED = 1     # Forced abilities
    AFTER = 2      # "After..." effects
    REACTION = 3   # [reaction] triggered abilities


class ChaosTokenType(Enum):
    PLUS_1 = "+1"
    ZERO = "0"
    MINUS_1 = "-1"
    MINUS_2 = "-2"
    MINUS_3 = "-3"
    MINUS_4 = "-4"
    MINUS_5 = "-5"
    MINUS_6 = "-6"
    MINUS_7 = "-7"
    MINUS_8 = "-8"
    SKULL = "skull"
    CULTIST = "cultist"
    TABLET = "tablet"
    ELDER_THING = "elder_thing"
    AUTO_FAIL = "auto_fail"
    ELDER_SIGN = "elder_sign"
    BLESS = "bless"
    CURSE = "curse"
    FROST = "frost"


# Numeric modifiers for standard tokens
CHAOS_TOKEN_VALUES: dict[ChaosTokenType, int | None] = {
    ChaosTokenType.PLUS_1: 1,
    ChaosTokenType.ZERO: 0,
    ChaosTokenType.MINUS_1: -1,
    ChaosTokenType.MINUS_2: -2,
    ChaosTokenType.MINUS_3: -3,
    ChaosTokenType.MINUS_4: -4,
    ChaosTokenType.MINUS_5: -5,
    ChaosTokenType.MINUS_6: -6,
    ChaosTokenType.MINUS_7: -7,
    ChaosTokenType.MINUS_8: -8,
    # Symbol tokens have scenario-dependent values
    ChaosTokenType.SKULL: None,
    ChaosTokenType.CULTIST: None,
    ChaosTokenType.TABLET: None,
    ChaosTokenType.ELDER_THING: None,
    ChaosTokenType.AUTO_FAIL: None,
    ChaosTokenType.ELDER_SIGN: None,
    ChaosTokenType.BLESS: 2,
    ChaosTokenType.CURSE: -2,
    ChaosTokenType.FROST: -1,
}
