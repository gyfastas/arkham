"""Tests for Otherworld Codex (Level 2)."""

import pytest
from backend.cards.seeker.otherworld_codex_lv2 import OtherworldCodex
from backend.engine.event_bus import EventBus
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, LocationState, ScenarioState,
)
from backend.tests.conftest import (
    make_enemy_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    inv_data = make_investigator_data()
    state.card_database[inv_data.id] = inv_data
    loc_data = make_location_data()
    state.card_database[loc_data.id] = loc_data
    cultist = make_enemy_data(id="cultist_x", health=2)
    state.card_database["cultist_x"] = cultist
    elite = make_enemy_data(id="elite_x", keywords=["elite"])
    state.card_database["elite_x"] = elite

    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="test_location",
    )
    state.investigators["inv1"] = inv
    loc = LocationState(location_id="test_location", card_data=loc_data, clues=0)
    state.locations["test_location"] = loc

    # 遭遇牌堆顶9张：精英在前，cultist 在后
    state.scenario.encounter_deck = (
        ["elite_x", "cultist_x"] + ["filler"] * 8
    )
    # 场上有一张 cultist_x
    enemy = CardInstance(
        instance_id="e1", card_id="cultist_x",
        owner_id="scenario", controller_id="scenario",
    )
    state.cards_in_play["e1"] = enemy
    loc.enemies.append("e1")

    inst = CardInstance(
        instance_id="codex_1", card_id="otherworld_codex_lv2",
        owner_id="inv1", controller_id="inv1",
    )
    inst.uses = {"secretss": 3}  # 生产数据的双 s 键
    state.cards_in_play["codex_1"] = inst
    inv.play_area.append("codex_1")

    impl = OtherworldCodex("codex_1")
    impl.register(bus, "codex_1")
    return state, bus, inv, loc, inst, impl


class TestOtherworldCodex:
    def test_discards_in_play_copy(self, setup):
        """自动选中顶9张中首个有场上副本的非精英卡：丢弃场上副本。"""
        state, bus, inv, loc, inst, impl = setup
        assert impl.activate(state, "inv1") is True
        assert "e1" not in state.cards_in_play
        assert "e1" not in loc.enemies
        assert "cultist_x" in state.scenario.encounter_discard
        assert inst.uses["secretss"] == 2
        assert inst.exhausted is True
        # 遭遇牌堆未丢失卡牌（9张洗回）
        assert len(state.scenario.encounter_deck) == 10

    def test_skips_elite(self, setup):
        """精英卡不可选（顶部的 elite_x 被跳过，选中 cultist_x）。"""
        state, bus, inv, loc, inst, impl = setup
        # elite_x 在顶部且场上无副本，cultist_x 有副本 → 选 cultist_x
        assert impl.activate(state, "inv1", choose_card_id="elite_x") is False
        assert impl.activate(state, "inv1", choose_card_id="cultist_x") is True

    def test_no_copy_in_play_only_shuffles(self, setup):
        """顶9张没有场上副本：只洗回（激活费用照常支付）。"""
        state, bus, inv, loc, inst, impl = setup
        loc.enemies.remove("e1")
        state.cards_in_play.pop("e1")
        assert impl.activate(state, "inv1") is True
        assert inst.uses["secretss"] == 2  # 费用已支付
        assert inst.exhausted is True
        assert state.scenario.encounter_discard == []
