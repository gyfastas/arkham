"""Test fixtures and helpers for Arkham Horror LCG backend tests."""

from __future__ import annotations

import pytest

from backend.cards.registry import CardRegistry
from backend.engine.actions import ActionResolver
from backend.engine.damage import DamageEngine
from backend.engine.event_bus import EventBus
from backend.engine.game import Game
from backend.engine.skill_test import SkillTestEngine
from backend.engine.slots import SlotManager
from backend.models.chaos import ChaosBag
from backend.models.enums import CardType, ChaosTokenType, PlayerClass, Skill, SlotType
from backend.models.investigator import InvestigatorCard, DeckRequirement
from backend.models.state import (
    CardData, CardInstance, GameState, InvestigatorState,
    LocationState, ScenarioState, SkillValues,
)


def make_investigator_data(
    id: str = "test_investigator",
    name: str = "Test Investigator",
    willpower: int = 3,
    intellect: int = 3,
    combat: int = 3,
    agility: int = 3,
    health: int = 7,
    sanity: int = 7,
) -> CardData:
    return CardData(
        id=id,
        name=name,
        name_cn=f"测试调查员",
        type=CardType.INVESTIGATOR,
        card_class=PlayerClass.NEUTRAL,
        health=health,
        sanity=sanity,
        skills=SkillValues(
            willpower=willpower,
            intellect=intellect,
            combat=combat,
            agility=agility,
        ),
    )


def make_investigator_card(
    id: str = "test_investigator",
    name: str = "Test Investigator",
    name_cn: str = "测试调查员",
    card_class: PlayerClass = PlayerClass.NEUTRAL,
    willpower: int = 3,
    intellect: int = 3,
    combat: int = 3,
    agility: int = 3,
    health: int = 7,
    sanity: int = 7,
    deck_requirement: DeckRequirement | None = None,
) -> InvestigatorCard:
    return InvestigatorCard(
        id=id,
        name=name,
        name_cn=name_cn,
        card_class=card_class,
        health=health,
        sanity=sanity,
        skills=SkillValues(
            willpower=willpower,
            intellect=intellect,
            combat=combat,
            agility=agility,
        ),
        deck_requirement=deck_requirement,
    )


def make_asset_data(
    id: str = "test_asset",
    name: str = "Test Asset",
    cost: int = 2,
    card_class: PlayerClass = PlayerClass.NEUTRAL,
    slots: list[SlotType] | None = None,
    health: int | None = None,
    sanity: int | None = None,
    skill_icons: dict | None = None,
    keywords: list[str] | None = None,
    uses: dict[str, int] | None = None,
    traits: list[str] | None = None,
) -> CardData:
    return CardData(
        id=id,
        name=name,
        name_cn=f"测试支援",
        type=CardType.ASSET,
        card_class=card_class,
        cost=cost,
        slots=slots or [],
        health=health,
        sanity=sanity,
        skill_icons=skill_icons or {},
        keywords=keywords or [],
        uses=uses,
        traits=traits or [],
    )


def make_event_data(
    id: str = "test_event",
    name: str = "Test Event",
    cost: int = 0,
    card_class: PlayerClass = PlayerClass.NEUTRAL,
    fast: bool = False,
) -> CardData:
    return CardData(
        id=id,
        name=name,
        name_cn=f"测试事件",
        type=CardType.EVENT,
        card_class=card_class,
        cost=cost,
        fast=fast,
    )


def make_skill_data(
    id: str = "test_skill",
    name: str = "Test Skill",
    card_class: PlayerClass = PlayerClass.NEUTRAL,
    skill_icons: dict | None = None,
) -> CardData:
    return CardData(
        id=id,
        name=name,
        name_cn=f"测试技能",
        type=CardType.SKILL,
        card_class=card_class,
        skill_icons=skill_icons or {"wild": 1},
    )


def make_enemy_data(
    id: str = "test_enemy",
    name: str = "Test Enemy",
    fight: int = 3,
    health: int = 3,
    evade: int = 3,
    damage: int = 1,
    horror: int = 1,
    keywords: list[str] | None = None,
) -> CardData:
    return CardData(
        id=id,
        name=name,
        name_cn=f"测试敌人",
        type=CardType.ENEMY,
        enemy_fight=fight,
        enemy_health=health,
        enemy_evade=evade,
        enemy_damage=damage,
        enemy_horror=horror,
        keywords=keywords or [],
    )


def make_location_data(
    id: str = "test_location",
    name: str = "Test Location",
    shroud: int = 2,
    clue_value: int = 2,
    connections: list[str] | None = None,
) -> CardData:
    return CardData(
        id=id,
        name=name,
        name_cn=f"测试地点",
        type=CardType.LOCATION,
        shroud=shroud,
        clue_value=clue_value,
        connections=connections or [],
    )


@pytest.fixture
def event_bus():
    return EventBus()


@pytest.fixture
def chaos_bag():
    bag = ChaosBag()
    bag.seed(42)
    return bag


@pytest.fixture
def game():
    """Create a minimal game with 1 investigator and 1 location."""
    g = Game("test_scenario")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data()
    g.register_card_data(inv_data)

    loc_data = make_location_data(clue_value=3, connections=[])
    g.register_card_data(loc_data)

    g.add_investigator("test_investigator", inv_data, starting_location="test_location")
    g.add_location("test_location", loc_data, clues=3)

    return g


@pytest.fixture
def game_with_enemy(game):
    """Game fixture with an enemy engaged with the investigator."""
    enemy_data = make_enemy_data()
    game.register_card_data(enemy_data)

    enemy_instance = CardInstance(
        instance_id="enemy_1",
        card_id="test_enemy",
        owner_id="scenario",
        controller_id="scenario",
    )
    game.state.cards_in_play["enemy_1"] = enemy_instance

    inv = game.state.get_investigator("test_investigator")
    inv.threat_area.append("enemy_1")

    return game
