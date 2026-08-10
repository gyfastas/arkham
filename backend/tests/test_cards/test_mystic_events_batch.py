"""Tests for Tides of Fate, Ward of Radiance, Stargazing, The Stars Are Right,
Winds of Power, Word of Command — 事件卡批次。"""

import pytest

from backend.cards.mystic.stargazing_lv1 import Stargazing
from backend.cards.mystic.the_stars_are_right_lv0 import TheStarsAreRight
from backend.cards.mystic.tides_of_fate_lv0 import TidesOfFate
from backend.cards.mystic.ward_of_radiance_lv0 import WardOfRadiance
from backend.cards.mystic.winds_of_power_lv1 import WindsOfPower
from backend.cards.mystic.word_of_command_lv2 import WordOfCommand
from backend.engine.event_bus import EventBus, EventContext
from backend.models.chaos import ChaosBag
from backend.models.enums import CardType, ChaosTokenType, GameEvent
from backend.models.state import (
    CardData, CardInstance, GameState, InvestigatorState, ScenarioState,
)
from backend.tests.conftest import (
    make_asset_data, make_event_data, make_investigator_data,
    make_skill_data,
)


def _base_state(hand=None, deck=None, resources=5):
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()
    inv_data = make_investigator_data()
    state.card_database[inv_data.id] = inv_data
    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1",
        hand=list(hand or []), deck=list(deck or []),
    )
    inv.resources = resources
    state.investigators["inv1"] = inv
    return state, bus, inv


def _emit(bus, state, event, inv_id="inv1", **kwargs):
    ctx = EventContext(game_state=state, event=event, investigator_id=inv_id, **kwargs)
    bus.emit(ctx)
    return ctx


class TestTidesOfFate:
    CID = "tides_of_fate_lv0"

    def _setup(self, tokens):
        state, bus, inv = _base_state()
        bag = ChaosBag(tokens=list(tokens))
        bag.seed(42)
        impl = TidesOfFate("evt1")
        impl.register(bus, "evt1")
        impl.bind_chaos_bag(bag)
        return state, bus, inv, bag, impl

    def test_curse_become_bless_then_swap_back(self):
        state, bus, inv, bag, impl = self._setup(
            [ChaosTokenType.CURSE, ChaosTokenType.CURSE, ChaosTokenType.ZERO])
        _emit(bus, state, GameEvent.CARD_PLAYED, extra={"card_id": self.CID})
        assert bag.tokens.count(ChaosTokenType.CURSE) == 0
        assert bag.tokens.count(ChaosTokenType.BLESS) == 2
        assert bag.tokens.count(ChaosTokenType.ZERO) == 1
        _emit(bus, state, GameEvent.ROUND_ENDS)
        assert bag.tokens.count(ChaosTokenType.BLESS) == 0
        assert bag.tokens.count(ChaosTokenType.CURSE) == 2

    def test_no_curse_no_change(self):
        state, bus, inv, bag, impl = self._setup([ChaosTokenType.ZERO])
        _emit(bus, state, GameEvent.CARD_PLAYED, extra={"card_id": self.CID})
        assert bag.tokens == [ChaosTokenType.ZERO]


class TestWardOfRadiance:
    CID = "ward_of_radiance_lv0"

    def _setup(self, tokens, holder_location="loc1", drawer_location="loc1"):
        state, bus, inv = _base_state(hand=[self.CID], resources=0)
        inv.location_id = holder_location
        drawer_data = make_investigator_data(id="inv2")
        state.card_database["inv2"] = drawer_data
        drawer = InvestigatorState(
            investigator_id="inv2", card_data=drawer_data,
            location_id=drawer_location)
        state.investigators["inv2"] = drawer
        state.card_database[self.CID] = make_event_data(id=self.CID, cost=0,
                                                        fast=True)
        treachery = CardData(
            id="treachery1", name="Treachery", name_cn="诡计",
            type=CardType.TREACHERY,
        )
        state.card_database["treachery1"] = treachery
        bag = ChaosBag(tokens=list(tokens))
        bag.seed(42)
        impl = WardOfRadiance("evt1")
        impl.register(bus, "evt1")
        impl.bind_chaos_bag(bag)
        return state, bus, inv, bag, impl

    def test_cancel_with_elder_sign_revealed(self):
        tokens = [ChaosTokenType.ELDER_SIGN] + [ChaosTokenType.MINUS_1] * 4
        state, bus, inv, bag, impl = self._setup(tokens)
        ctx = _emit(bus, state, GameEvent.ENCOUNTER_CARD_DRAWN, inv_id="inv2",
                    extra={"card_id": "treachery1"})
        assert state.scenario.vars["cancelled_encounter"] == "treachery1"
        assert ctx.extra["ward_of_radiance_cancelled"] == "treachery1"
        assert self.CID not in inv.hand
        assert self.CID in inv.discard
        assert len(ctx.extra["ward_of_radiance_revealed"]) == 5
        # 袋未被消耗
        assert len(bag.tokens) == 5

    def test_no_cancel_without_bless_or_elder_sign(self):
        tokens = [ChaosTokenType.MINUS_1] * 6
        state, bus, inv, bag, impl = self._setup(tokens)
        ctx = _emit(bus, state, GameEvent.ENCOUNTER_CARD_DRAWN, inv_id="inv2",
                    extra={"card_id": "treachery1"})
        assert "cancelled_encounter" not in state.scenario.vars
        assert "ward_of_radiance_cancelled" not in ctx.extra
        # 仍然打出并弃置
        assert self.CID in inv.discard

    def test_holder_at_other_location_no_trigger(self):
        tokens = [ChaosTokenType.BLESS] * 5
        state, bus, inv, bag, impl = self._setup(tokens, drawer_location="loc2")
        _emit(bus, state, GameEvent.ENCOUNTER_CARD_DRAWN, inv_id="inv2",
              extra={"card_id": "treachery1"})
        assert "cancelled_encounter" not in state.scenario.vars
        assert self.CID in inv.hand  # 未打出


class TestStargazing:
    CID = "stargazing_lv1"

    def test_shuffle_stars_into_top_10(self):
        state, bus, inv = _base_state()
        state.scenario.encounter_deck = [f"enc_{i}" for i in range(12)]
        impl = Stargazing("evt1")
        impl.register(bus, "evt1")
        ctx = _emit(bus, state, GameEvent.CARD_PLAYED,
                    extra={"card_id": self.CID})
        deck = state.scenario.encounter_deck
        assert len(deck) == 13
        assert "the_stars_are_right_lv0" in deck[:10]
        assert state.scenario.vars["stargazing_played"] == 1

    def test_requires_10_cards(self):
        state, bus, inv = _base_state()
        state.scenario.encounter_deck = ["enc_0"] * 5
        impl = Stargazing("evt1")
        impl.register(bus, "evt1")
        _emit(bus, state, GameEvent.CARD_PLAYED, extra={"card_id": self.CID})
        assert "the_stars_are_right_lv0" not in state.scenario.encounter_deck
        assert "stargazing_played" not in state.scenario.vars


class TestTheStarsAreRight:
    CID = "the_stars_are_right_lv0"

    def test_revelation_effect(self):
        state, bus, inv = _base_state(deck=["guts_lv0"], resources=3)
        inv.actions_remaining = 0
        impl = TheStarsAreRight("evt1")
        impl.register(bus, "evt1")
        ctx = _emit(bus, state, GameEvent.ENCOUNTER_CARD_DRAWN,
                    extra={"card_id": self.CID})
        assert "guts_lv0" in inv.hand       # 抽1张牌
        assert inv.resources == 4           # +1资源
        assert inv.actions_remaining == 1   # 立即行动（近似）
        assert self.CID in state.scenario.vars["removed_from_game"]
        assert state.scenario.vars["cancelled_encounter"] == self.CID
        assert ctx.extra["stars_are_right_chosen"] == "inv1"

    def test_stripped_from_encounter_discard(self):
        state, bus, inv = _base_state()
        impl = TheStarsAreRight("evt1")
        impl.register(bus, "evt1")
        _emit(bus, state, GameEvent.ENCOUNTER_CARD_DRAWN,
              extra={"card_id": self.CID})
        # phase_mythos 会将其送入遭遇弃牌堆
        state.scenario.encounter_discard.append(self.CID)
        _emit(bus, state, GameEvent.ROUND_BEGINS)
        assert self.CID not in state.scenario.encounter_discard


class TestWindsOfPower:
    CID = "winds_of_power_lv1"

    def _setup(self, hand=None, resources=5):
        state, bus, inv = _base_state(hand=hand, resources=resources)
        state.card_database[self.CID] = make_event_data(id=self.CID, cost=2)
        state.card_database["spell_asset"] = make_asset_data(
            id="spell_asset", traits=["spell"], uses={"charges": 1})
        asset = CardInstance(
            instance_id="asset1", card_id="spell_asset",
            owner_id="inv1", controller_id="inv1",
        )
        asset.uses = {"charges": 1}
        state.cards_in_play["asset1"] = asset
        inv.play_area.append("asset1")
        impl = WindsOfPower("evt1")
        impl.register(bus, "evt1")
        return state, bus, inv, asset, impl

    def test_play_places_two_charges(self):
        state, bus, inv, asset, impl = self._setup()
        _emit(bus, state, GameEvent.CARD_PLAYED, extra={"card_id": self.CID})
        assert asset.uses["charges"] == 3

    def test_autoplay_when_drawn_during_turn(self):
        state, bus, inv, asset, impl = self._setup(hand=[self.CID])
        _emit(bus, state, GameEvent.INVESTIGATOR_TURN_BEGINS)
        _emit(bus, state, GameEvent.CARD_DRAWN, extra={"card_id": self.CID})
        assert self.CID not in inv.hand
        assert self.CID in inv.discard
        assert inv.resources == 3  # 支付2
        assert asset.uses["charges"] == 3

    def test_no_autoplay_outside_turn(self):
        state, bus, inv, asset, impl = self._setup(hand=[self.CID])
        _emit(bus, state, GameEvent.CARD_DRAWN, extra={"card_id": self.CID})
        assert self.CID in inv.hand
        assert asset.uses["charges"] == 1


class TestWordOfCommand:
    CID = "word_of_command_lv2"

    def test_draws_first_spell_from_deck(self):
        state, bus, inv = _base_state(
            deck=["guts_lv0", "shrivelling_lv0", "ward_of_protection_lv0"])
        state.card_database["guts_lv0"] = make_skill_data(id="guts_lv0")
        state.card_database["shrivelling_lv0"] = make_asset_data(
            id="shrivelling_lv0", traits=["spell"])
        state.card_database["ward_of_protection_lv0"] = make_event_data(
            id="ward_of_protection_lv0")
        state.card_database["ward_of_protection_lv0"].traits = ["spell", "spirit"]
        impl = WordOfCommand("evt1")
        impl.register(bus, "evt1")
        ctx = _emit(bus, state, GameEvent.CARD_PLAYED,
                    extra={"card_id": self.CID})
        assert "shrivelling_lv0" in inv.hand
        assert "shrivelling_lv0" not in inv.deck
        assert len(inv.deck) == 2
        assert ctx.extra["word_of_command_drawn"] == "shrivelling_lv0"

    def test_no_spell_in_deck(self):
        state, bus, inv = _base_state(deck=["guts_lv0"])
        state.card_database["guts_lv0"] = make_skill_data(id="guts_lv0")
        impl = WordOfCommand("evt1")
        impl.register(bus, "evt1")
        _emit(bus, state, GameEvent.CARD_PLAYED, extra={"card_id": self.CID})
        assert inv.hand == []
        assert len(inv.deck) == 1
