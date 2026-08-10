"""Tests for Arcane Research / Down the Rabbit Hole (Permanent, 战役升级类).

奥术研究：购买时1精神创伤（每场冒险开始1恐惧）；每场冒险第一张法术升级-1经验。
掉进兔子洞：每场冒险前2张升级各-1经验；购买新卡+1经验。
"""

import pytest
from backend.cards.mystic.arcane_research_lv0 import ArcaneResearch
from backend.cards.mystic.down_the_rabbit_hole_lv0 import DownTheRabbitHole
from backend.models.state import GameState, InvestigatorState, ScenarioState
from backend.tests.conftest import (
    make_asset_data, make_event_data, make_investigator_data,
)


@pytest.fixture
def state():
    s = GameState(scenario=ScenarioState(scenario_id="test"))
    inv_data = make_investigator_data()
    s.card_database[inv_data.id] = inv_data
    s.investigators["inv1"] = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1")
    return s


class TestArcaneResearch:
    def test_mental_trauma_at_scenario_start(self, state):
        """精神创伤：每场冒险开始受到1恐惧。"""
        impl = ArcaneResearch("impl_ar")
        assert impl.apply_scenario_start_trauma(state, "inv1") is True
        assert state.get_investigator("inv1").horror == 1

    def test_first_spell_upgrade_discounted(self, state):
        """每场冒险第一张法术升级-1经验（消费型）。"""
        impl = ArcaneResearch("impl_ar")
        spell = make_event_data(id="s", name="S")
        spell.traits = ["spell"]
        tactic = make_event_data(id="t", name="T")
        tactic.traits = ["tactic"]
        assert impl.upgrade_discount(tactic) == 0   # 非法术不折扣
        assert impl.upgrade_discount(spell) == 1    # 第一张法术-1
        assert impl.upgrade_discount(spell) == 0    # 仅第一张
        impl.reset_scenario()
        assert impl.upgrade_discount(spell) == 1    # 新冒险重置


class TestDownTheRabbitHole:
    def test_first_two_upgrades_discounted(self):
        """每场冒险前2张升级各-1经验。"""
        impl = DownTheRabbitHole("impl_drh")
        assert impl.upgrade_discount() == 1
        assert impl.upgrade_discount() == 1
        assert impl.upgrade_discount() == 0
        impl.reset_scenario()
        assert impl.upgrade_discount() == 1

    def test_new_card_penalty(self):
        """购买新卡经验+1（恒定）。"""
        impl = DownTheRabbitHole("impl_drh")
        assert impl.new_card_cost_modifier() == 1
        impl.upgrade_discount()
        impl.upgrade_discount()
        assert impl.new_card_cost_modifier() == 1  # 不受升级计数影响
