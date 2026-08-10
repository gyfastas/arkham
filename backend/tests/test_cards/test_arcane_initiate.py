"""Tests for Arcane Initiate (Level 0). (01063)

强制 - 进场后：在其上放置1个毁灭标记。
【快速】横置：搜索牌库顶3张牌，选择1张法术卡抽取，然后洗牌。
"""

import pytest
from backend.cards.mystic.arcane_initiate_lv0 import ArcaneInitiate
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, ScenarioState,
)
from backend.tests.conftest import make_asset_data, make_event_data, make_investigator_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    inv_data = make_investigator_data()
    state.card_database[inv_data.id] = inv_data
    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1",
    )
    state.investigators["inv1"] = inv

    state.card_database["arcane_initiate_lv0"] = make_asset_data(
        id="arcane_initiate_lv0", name="Arcane Initiate",
        traits=["ally", "sorcerer"], health=1, sanity=2,
    )
    state.card_database["shrivelling_lv0"] = make_asset_data(
        id="shrivelling_lv0", name="Shrivelling", traits=["spell"],
    )
    state.card_database["blinding_light_lv0"] = make_event_data(
        id="blinding_light_lv0", name="Blinding Light",
    )
    state.card_database["blinding_light_lv0"].traits = ["spell"]
    state.card_database["machete_lv0"] = make_asset_data(
        id="machete_lv0", name="Machete", traits=["item", "weapon"],
    )

    inst = CardInstance(
        instance_id="inst_ai", card_id="arcane_initiate_lv0",
        owner_id="inv1", controller_id="inv1",
    )
    state.cards_in_play["inst_ai"] = inst
    inv.play_area.append("inst_ai")

    impl = ArcaneInitiate("inst_ai")
    impl.register(bus, "inst_ai")
    return state, bus, inv, inst, impl


class TestArcaneInitiate:
    def test_doom_placed_on_enter_play(self, setup):
        """强制：进场后在其上放置1个毁灭标记。"""
        state, bus, inv, inst, impl = setup
        ctx = EventContext(
            game_state=state, event=GameEvent.CARD_ENTERS_PLAY,
            investigator_id="inv1", target="inst_ai",
            extra={"card_id": "arcane_initiate_lv0"},
        )
        bus.emit(ctx)
        assert inst.doom == 1
        assert ctx.extra["arcane_initiate_doom"] is True

    def test_no_doom_for_other_cards(self, setup):
        state, bus, inv, inst, impl = setup
        other = CardInstance(
            instance_id="inst_other", card_id="machete_lv0",
            owner_id="inv1", controller_id="inv1",
        )
        state.cards_in_play["inst_other"] = other
        bus.emit(EventContext(
            game_state=state, event=GameEvent.CARD_ENTERS_PLAY,
            investigator_id="inv1", target="inst_other",
        ))
        assert inst.doom == 0

    def test_activate_searches_top3_and_draws_spell(self, setup):
        """横置发动：只搜牌库顶3张；命中法术卡则抽取并洗牌。"""
        state, bus, inv, inst, impl = setup
        # 法术在第3张（顶3之内）
        inv.deck = ["machete_lv0", "machete_lv0", "shrivelling_lv0", "machete_lv0"]
        assert impl.activate(state, "inv1") is True
        assert inst.exhausted is True
        assert "shrivelling_lv0" in inv.hand
        assert len(inv.deck) == 3

    def test_activate_ignores_spell_beyond_top3(self, setup):
        """法术在第4张（顶3之外）：不抽取，但仍洗牌。"""
        state, bus, inv, inst, impl = setup
        inv.deck = ["machete_lv0", "machete_lv0", "machete_lv0", "shrivelling_lv0"]
        assert impl.activate(state, "inv1") is True
        assert "shrivelling_lv0" not in inv.hand
        assert len(inv.deck) == 4

    def test_activate_draws_spell_event_too(self, setup):
        """官方卡面为"Spell 卡"（不限支援）：法术事件也可抽取。"""
        state, bus, inv, inst, impl = setup
        inv.deck = ["blinding_light_lv0", "machete_lv0"]
        assert impl.activate(state, "inv1") is True
        assert "blinding_light_lv0" in inv.hand

    def test_cannot_activate_while_exhausted(self, setup):
        state, bus, inv, inst, impl = setup
        inst.exhausted = True
        inv.deck = ["shrivelling_lv0"]
        assert impl.activate(state, "inv1") is False
        assert "shrivelling_lv0" not in inv.hand
