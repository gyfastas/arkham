"""Tests for Torrent of Power (Level 0). (03235)

投入时从你控制的支援卡花费至多3充能：每充能本卡获得[willpower][wild]
（意志检定每充能+2图标，其他检定+1）。
"""

import pytest
from backend.cards.mystic.torrent_of_power_lv0 import TorrentOfPower
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent, Skill
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, ScenarioState,
)
from backend.tests.conftest import (
    make_asset_data, make_investigator_data, make_skill_data,
)


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

    state.card_database["torrent_of_power_lv0"] = make_skill_data(
        id="torrent_of_power_lv0", name="Torrent of Power",
    )
    state.card_database["shrivelling_lv0"] = make_asset_data(
        id="shrivelling_lv0", name="Shrivelling", traits=["spell"],
        uses={"charges": 4},
    )
    state.card_database["scrying_lv0"] = make_asset_data(
        id="scrying_lv0", name="Scrying", traits=["spell"],
        uses={"charges": 3},
    )

    impl = TorrentOfPower("inst_top")
    impl.register(bus, "inst_top")
    return state, bus, inv, impl


def _add_charges(state, inv, instance_id, card_id, charges):
    inst = CardInstance(
        instance_id=instance_id, card_id=card_id,
        owner_id="inv1", controller_id="inv1",
    )
    inst.uses = {"charges": charges}
    state.cards_in_play[instance_id] = inst
    inv.play_area.append(instance_id)
    return inst


def _commit_ctx(state, skill, **extra):
    return EventContext(
        game_state=state, event=GameEvent.SKILL_TEST_COMMIT,
        investigator_id="inv1", skill_type=skill, difficulty=2,
        committed_cards=["torrent_of_power_lv0"], amount=1, extra=extra,
    )


class TestTorrentOfPower:
    def test_spends_up_to_3_charges_willpower_test(self, setup):
        """意志检定：花3充能，每充能+2图标（[willpower][wild]）。"""
        state, bus, inv, impl = setup
        shriv = _add_charges(state, inv, "inst_shriv", "shrivelling_lv0", 4)
        ctx = _commit_ctx(state, Skill.WILLPOWER)
        bus.emit(ctx)
        assert ctx.extra["torrent_of_power_spent"] == 3
        assert shriv.uses["charges"] == 1
        assert ctx.amount == 1 + 3 * 2  # 印刷野性1 + 每充能2

    def test_other_skill_gets_1_per_charge(self, setup):
        """非意志检定：每充能仅[wild]生效（+1）。"""
        state, bus, inv, impl = setup
        _add_charges(state, inv, "inst_shriv", "shrivelling_lv0", 4)
        ctx = _commit_ctx(state, Skill.COMBAT)
        bus.emit(ctx)
        assert ctx.amount == 1 + 3 * 1

    def test_spends_across_multiple_assets(self, setup):
        """充能可分散花费在多张支援卡上。"""
        state, bus, inv, impl = setup
        shriv = _add_charges(state, inv, "inst_shriv", "shrivelling_lv0", 2)
        scry = _add_charges(state, inv, "inst_scry", "scrying_lv0", 2)
        ctx = _commit_ctx(state, Skill.WILLPOWER)
        bus.emit(ctx)
        assert ctx.extra["torrent_of_power_spent"] == 3
        assert shriv.uses["charges"] + scry.uses["charges"] == 1

    def test_capped_by_available_charges(self, setup):
        """只有1充能时只花1。"""
        state, bus, inv, impl = setup
        shriv = _add_charges(state, inv, "inst_shriv", "shrivelling_lv0", 1)
        ctx = _commit_ctx(state, Skill.WILLPOWER)
        bus.emit(ctx)
        assert ctx.extra["torrent_of_power_spent"] == 1
        assert shriv.uses["charges"] == 0
        assert ctx.amount == 1 + 2

    def test_explicit_zero_charges(self, setup):
        """charges_to_spend=0：不花充能不加图标。"""
        state, bus, inv, impl = setup
        shriv = _add_charges(state, inv, "inst_shriv", "shrivelling_lv0", 4)
        ctx = _commit_ctx(state, Skill.WILLPOWER, charges_to_spend=0)
        bus.emit(ctx)
        assert "torrent_of_power_spent" not in ctx.extra
        assert shriv.uses["charges"] == 4
        assert ctx.amount == 1

    def test_no_effect_when_not_committed(self, setup):
        state, bus, inv, impl = setup
        shriv = _add_charges(state, inv, "inst_shriv", "shrivelling_lv0", 4)
        ctx = EventContext(
            game_state=state, event=GameEvent.SKILL_TEST_COMMIT,
            investigator_id="inv1", skill_type=Skill.WILLPOWER,
            difficulty=2, committed_cards=[], amount=0,
        )
        bus.emit(ctx)
        assert shriv.uses["charges"] == 4
        assert ctx.amount == 0
