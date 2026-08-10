"""Tests for Peter Sylvestre (Level 0)."""

import pytest
from backend.cards.survivor.peter_sylvestre_lv0 import PeterSylvestre
from backend.models.enums import (
    ChaosTokenType, GameEvent, PlayerClass, Skill, SlotType,
)
from backend.engine.event_bus import EventContext
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_investigator_data, make_asset_data, make_location_data,
)
from backend.engine.game import Game


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)
    inv_data = make_investigator_data(agility=3)
    g.register_card_data(inv_data)
    loc = make_location_data()
    g.register_card_data(loc)

    pete_data = make_asset_data(
        id="peter_sylvestre_lv0", name="Peter Sylvestre", cost=3,
        card_class=PlayerClass.SURVIVOR,
        slots=[SlotType.ALLY], health=1, sanity=2,
        traits=["ally", "miskatonic"],
    )
    g.register_card_data(pete_data)
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)
    g.card_registry.register_class(PeterSylvestre)
    return g


def _put_pete_in_play(game, horror=0):
    inv = game.state.get_investigator("inv1")
    iid = game.state.next_instance_id()
    game.state.cards_in_play[iid] = CardInstance(
        instance_id=iid, card_id="peter_sylvestre_lv0",
        owner_id="inv1", controller_id="inv1",
        slot_used=[SlotType.ALLY], horror=horror,
    )
    inv.play_area.append(iid)
    game.card_registry.activate_card("peter_sylvestre_lv0", iid, game.event_bus)
    return iid


def _turn_ends(game, investigator_id="inv1"):
    game.event_bus.emit(EventContext(
        game_state=game.state,
        event=GameEvent.INVESTIGATOR_TURN_ENDS,
        investigator_id=investigator_id,
    ))


class TestPeterSylvestre:
    def test_card_registered(self, game):
        assert "peter_sylvestre_lv0" in game.card_registry.registered_cards

    def test_agility_bonus(self, game):
        """+1 敏捷。"""
        _put_pete_in_play(game)
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]

        result = game.skill_test_engine.run_test("inv1", Skill.AGILITY, 4)

        assert result.modified_skill == 4  # 3 + 1
        assert result.success is True

    def test_heals_1_horror_after_own_turn_ends(self, game):
        """你的回合结束后：治愈彼得·希尔维斯特1点恐惧。"""
        pete_id = _put_pete_in_play(game, horror=2)

        _turn_ends(game)

        assert game.state.get_card_instance(pete_id).horror == 1

    def test_no_heal_on_other_turn_end(self, game):
        pete_id = _put_pete_in_play(game, horror=2)

        _turn_ends(game, investigator_id="inv2")

        assert game.state.get_card_instance(pete_id).horror == 2

    def test_no_heal_at_zero_horror(self, game):
        pete_id = _put_pete_in_play(game, horror=0)

        _turn_ends(game)

        assert game.state.get_card_instance(pete_id).horror == 0
