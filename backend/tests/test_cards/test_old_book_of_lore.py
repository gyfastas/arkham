"""Tests for Old Book of Lore (Level 0)."""

import pytest
from backend.cards.seeker.old_book_of_lore_lv0 import OldBookOfLore
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent
from backend.models.state import GameState, InvestigatorState, LocationState, ScenarioState, CardInstance
from backend.tests.conftest import make_investigator_data, make_location_data, make_asset_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    inv_data = make_investigator_data(intellect=3)
    state.card_database[inv_data.id] = inv_data

    book_data = make_asset_data(
        id="old_book_of_lore_lv0", name="Old Book of Lore",
        traits=["tome"], skill_icons={"willpower": 1},
    )
    state.card_database["old_book_of_lore_lv0"] = book_data

    loc_data = make_location_data()
    state.card_database[loc_data.id] = loc_data

    inv = InvestigatorState(
        investigator_id="inv1",
        card_data=inv_data,
        location_id="test_location",
        deck=["card_a", "card_b", "card_c"],
    )
    state.investigators["inv1"] = inv

    loc = LocationState(location_id="test_location", card_data=loc_data, clues=2)
    state.locations["test_location"] = loc

    impl = OldBookOfLore("inst_book")
    impl.register(bus, "inst_book")

    ci = CardInstance(instance_id="inst_book", card_id="old_book_of_lore_lv0", owner_id="inv1", controller_id="inv1")
    state.cards_in_play["inst_book"] = ci
    inv.play_area.append("inst_book")

    return state, bus, inv, impl


class TestOldBookOfLore:
    def test_activate_searches_top3_and_shuffles(self, setup):
        """官方：消耗，查看牌库顶3张，抽1张，其余洗入牌库。"""
        state, bus, inv, impl = setup
        assert len(inv.deck) == 3
        assert len(inv.hand) == 0

        ok = impl.activate(state, "inv1")

        assert ok
        assert len(inv.hand) == 1
        assert inv.hand[0] == "card_a"  # 默认取第1张
        assert len(inv.deck) == 2
        assert set(inv.deck) == {"card_b", "card_c"}  # 其余洗入牌库
        ci = state.get_card_instance("inst_book")
        assert ci.exhausted is True  # 已消耗

    def test_activate_pick_index(self, setup):
        """pick_index 指定抽取顶3中的哪一张。"""
        state, bus, inv, impl = setup

        ok = impl.activate(state, "inv1", pick_index=1)

        assert ok
        assert inv.hand == ["card_b"]
        assert set(inv.deck) == {"card_a", "card_c"}

    def test_activate_fails_when_exhausted(self, setup):
        """已消耗时不能再启动。"""
        state, bus, inv, impl = setup
        state.get_card_instance("inst_book").exhausted = True

        ok = impl.activate(state, "inv1")

        assert ok is False
        assert len(inv.hand) == 0
        assert len(inv.deck) == 3

    def test_provides_willpower_icon(self, setup):
        """Old Book of Lore card data has willpower skill icon."""
        state, bus, inv, impl = setup
        card_data = state.card_database["old_book_of_lore_lv0"]
        assert card_data.skill_icons.get("willpower") == 1

    def test_tome_activate_uses_tome_action_not_regular(self, setup):
        """TOME_ACTIVATE should deduct tome_actions_remaining, NOT actions_remaining."""
        from backend.engine.actions import ActionResolver
        from backend.engine.skill_test import SkillTestEngine
        from backend.engine.damage import DamageEngine
        from backend.models.enums import Action
        from backend.cards.registry import CardRegistry

        state, bus, inv, impl = setup
        inv.actions_remaining = 3
        inv.tome_actions_remaining = 1

        from backend.models.chaos import ChaosBag
        st = SkillTestEngine(state, bus, ChaosBag())
        de = DamageEngine(state, bus)
        registry = CardRegistry()
        resolver = ActionResolver(state, bus, st, de, {}, registry)

        ok = resolver.perform_action("inv1", Action.TOME_ACTIVATE, instance_id="inst_book")
        assert ok is True
        # Tome action used, not regular action
        assert inv.tome_actions_remaining == 0
        assert inv.actions_remaining == 3  # unchanged!
        # Card should be exhausted
        ci = state.get_card_instance("inst_book")
        assert ci.exhausted is True

    def test_play_then_activate_costs(self, setup):
        """Playing Old Book of Lore costs 1 action, activating it costs 1 action (or tome action)."""
        state, bus, inv, impl = setup
        inv.actions_remaining = 3
        inv.tome_actions_remaining = 1
        inv.resources = 5

        # Put book in hand for playing
        inv.hand.append("old_book_of_lore_lv0")
        inv.play_area.remove("inst_book")
        del state.cards_in_play["inst_book"]

        from backend.engine.actions import ActionResolver
        from backend.engine.skill_test import SkillTestEngine
        from backend.engine.damage import DamageEngine
        from backend.models.enums import Action
        from backend.cards.registry import CardRegistry

        from backend.models.chaos import ChaosBag
        st = SkillTestEngine(state, bus, ChaosBag())
        de = DamageEngine(state, bus)
        registry = CardRegistry()
        resolver = ActionResolver(state, bus, st, de, {}, registry)

        # Play the card (1 action)
        ok = resolver.perform_action("inv1", Action.PLAY, card_id="old_book_of_lore_lv0")
        assert ok is True
        assert inv.actions_remaining == 2  # 3 - 1 = 2

        # Now activate via tome action (should use tome_actions, not regular)
        # Find the new instance
        new_inst = None
        for iid in inv.play_area:
            ci = state.get_card_instance(iid)
            if ci and ci.card_id == "old_book_of_lore_lv0":
                new_inst = iid
                break

        if new_inst:
            ok = resolver.perform_action("inv1", Action.TOME_ACTIVATE, instance_id=new_inst)
            assert ok is True
            assert inv.tome_actions_remaining == 0
            assert inv.actions_remaining == 2  # still 2, tome action was free
