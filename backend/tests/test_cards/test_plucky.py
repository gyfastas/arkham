"""Tests for Plucky (Level 1)."""

import pytest
from backend.cards.survivor.plucky_lv1 import Plucky
from backend.models.enums import GameEvent, PlayerClass, Skill
from backend.engine.event_bus import EventContext
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_asset_data, make_investigator_data, make_location_data,
)
from backend.engine.game import Game


@pytest.fixture
def game():
    g = Game("test")
    inv_data = make_investigator_data()
    g.register_card_data(inv_data)
    loc = make_location_data()
    g.register_card_data(loc)
    g.register_card_data(make_asset_data(
        id="plucky_lv1", name="Plucky", cost=1,
        card_class=PlayerClass.SURVIVOR, sanity=1, traits=["talent", "composure"],
    ))
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)
    g.card_registry.register_class(Plucky)
    return g


def _put_in_play(game):
    inv = game.state.get_investigator("inv1")
    iid = game.state.next_instance_id()
    game.state.cards_in_play[iid] = CardInstance(
        instance_id=iid, card_id="plucky_lv1",
        owner_id="inv1", controller_id="inv1",
    )
    inv.play_area.append(iid)
    impl = game.card_registry.activate_card(
        "plucky_lv1", iid, game.event_bus, chaos_bag=game.chaos_bag)
    return iid, impl


def _emit(game, event, inv_id="inv1", **kwargs):
    ctx = EventContext(
        game_state=game.state, event=event, investigator_id=inv_id, **kwargs)
    game.event_bus.emit(ctx)
    return ctx


class TestPlucky:
    def test_card_registered(self, game):
        assert "plucky_lv1" in game.card_registry.registered_cards

    def test_spend_boosts_willpower_and_intellect(self, game):
        """花1资源武装：下一次对应检定+1（可叠加两种技能）。"""
        iid, impl = _put_in_play(game)
        inv = game.state.get_investigator("inv1")
        inv.resources = 2

        assert impl.spend(game.state, "inv1", Skill.WILLPOWER) is True
        assert impl.spend(game.state, "inv1", Skill.INTELLECT) is True
        assert inv.resources == 0

        ctx = _emit(game, GameEvent.SKILL_VALUE_DETERMINED,
                    skill_type=Skill.WILLPOWER, amount=3)
        assert ctx.amount == 4
        ctx = _emit(game, GameEvent.SKILL_VALUE_DETERMINED,
                    skill_type=Skill.INTELLECT, amount=3)
        assert ctx.amount == 4
        # 一次性消耗：再次检定无加值
        ctx = _emit(game, GameEvent.SKILL_VALUE_DETERMINED,
                    skill_type=Skill.WILLPOWER, amount=3)
        assert ctx.amount == 3

    def test_spend_rejects_other_skills(self, game):
        iid, impl = _put_in_play(game)
        assert impl.spend(game.state, "inv1", Skill.COMBAT) is False

    def test_non_direct_horror_soaks_to_plucky_first(self, game):
        """非直接恐惧先由有胆有识承担：2恐惧中1点给有胆有识，1点给调查员。"""
        iid, _ = _put_in_play(game)
        inv = game.state.get_investigator("inv1")

        game.damage_engine.deal_damage("inv1", horror=2)
        # 有胆有识 sanity 1：承满1点被击败，剩余1点落到调查员
        assert game.state.get_card_instance(iid) is None
        assert "plucky_lv1" in inv.discard
        assert inv.horror == 1

    def test_soak_partial_leaves_plucky_in_play(self, game):
        """承恐未满时有胆有识留在场上（sanity 调为2，承1点不击败）。"""
        game.state.card_database["plucky_lv1"].sanity = 2
        iid, _ = _put_in_play(game)
        inv = game.state.get_investigator("inv1")

        game.damage_engine.deal_damage("inv1", horror=1)
        inst = game.state.get_card_instance(iid)
        assert inst is not None and inst.horror == 1
        assert iid in inv.play_area
        assert inv.horror == 0

    def test_no_soak_when_not_in_play(self, game):
        inv = game.state.get_investigator("inv1")
        game.damage_engine.deal_damage("inv1", horror=2)
        assert inv.horror == 2
