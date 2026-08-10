"""Tests for Knowledge is Power (Level 0)."""

import pytest
from backend.cards.seeker.knowledge_is_power_lv0 import KnowledgeIsPower
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent, PlayerClass
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, LocationState, ScenarioState,
)
from backend.tests.conftest import (
    make_asset_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    inv_data = make_investigator_data()
    state.card_database[inv_data.id] = inv_data
    loc_data = make_location_data()
    state.card_database[loc_data.id] = loc_data
    state.card_database["old_book_of_lore_lv0"] = make_asset_data(
        id="old_book_of_lore_lv0", cost=3, card_class=PlayerClass.SEEKER,
        traits=["item", "tome"])
    state.card_database["machete_x"] = make_asset_data(
        id="machete_x", cost=3, card_class=PlayerClass.GUARDIAN,
        traits=["item", "weapon"])
    for cid in ["d1", "d2", "d3", "d4"]:
        state.card_database[cid] = make_asset_data(id=cid, cost=1)

    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data,
        location_id="test_location",
        deck=["d1", "d2", "d3", "d4"],
    )
    state.investigators["inv1"] = inv
    state.locations["test_location"] = LocationState(
        location_id="test_location", card_data=loc_data,
    )

    obol = CardInstance(
        instance_id="obol_1", card_id="old_book_of_lore_lv0",
        owner_id="inv1", controller_id="inv1",
    )
    state.cards_in_play["obol_1"] = obol
    inv.play_area.append("obol_1")
    # 一张非书籍/法术支援作对照
    weapon = CardInstance(
        instance_id="wp_1", card_id="machete_x",
        owner_id="inv1", controller_id="inv1",
    )
    state.cards_in_play["wp_1"] = weapon
    inv.play_area.append("wp_1")

    impl = KnowledgeIsPower("kip_1")
    impl.register(bus, "kip_1")
    return state, bus, inv, obol, impl


def _play(state, bus, **extra):
    ctx = EventContext(
        game_state=state,
        event=GameEvent.CARD_PLAYED,
        investigator_id="inv1",
        extra={"card_id": "knowledge_is_power_lv0", **extra},
    )
    bus.emit(ctx)
    return ctx


class TestKnowledgeIsPower:
    def test_resolve_in_play_tome_ignoring_costs(self, setup):
        """自动选择场上古书：结算其能力（抽1张），消耗费用被忽略（不横置）。"""
        state, bus, inv, obol, impl = setup
        ctx = _play(state, bus)
        assert ctx.extra["knowledge_is_power_resolved"] == "old_book_of_lore_lv0"
        assert len(inv.hand) == 1  # 古书能力抽了1张
        assert obol.exhausted is False  # 忽略费用：横置被恢复

    def test_explicit_target_must_be_tome_or_spell(self, setup):
        """显式指定非书籍/法术支援：不结算。"""
        state, bus, inv, obol, impl = setup
        ctx = _play(state, bus, asset_instance_id="wp_1")
        assert "knowledge_is_power_resolved" not in ctx.extra
        assert inv.hand == []

    def test_reveal_from_hand_and_discard_to_draw(self, setup):
        """揭示手牌中的书籍结算其能力，然后丢弃它抽1张。"""
        state, bus, inv, obol, impl = setup
        inv.hand.append("old_book_of_lore_lv0")
        hand_before = len(inv.hand)

        ctx = _play(state, bus,
                    hand_card_id="old_book_of_lore_lv0",
                    discard_revealed=True)
        assert ctx.extra["knowledge_is_power_resolved"] == "old_book_of_lore_lv0"
        # 手牌变化：古书能力抽1张（+1），弃古书（-1），弃后抽1张（+1）→ 净+1
        assert "old_book_of_lore_lv0" in inv.discard
        assert len(inv.hand) == hand_before + 1
        # 手牌揭示的古书未进场
        assert not any(
            inst.card_id == "old_book_of_lore_lv0" and inst.instance_id != "obol_1"
            for inst in state.cards_in_play.values()
        )
