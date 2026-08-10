"""Tests for Blasphemous Covenant (Level 2). (07113)

[反应]你所在地点的调查员揭示[诅咒]标记时，横置：修正值视为+1。
"""

import pytest

from backend.cards.seeker.blasphemous_covenant_lv2 import BlasphemousCovenant
from backend.engine.game import Game
from backend.models.enums import ChaosTokenType, Skill
from backend.models.state import CardInstance
from backend.tests.conftest import make_asset_data, make_investigator_data, make_location_data


@pytest.fixture
def game():
    g = Game("test_covenant")
    g.chaos_bag.seed(42)
    inv_data = make_investigator_data(intellect=3)
    g.register_card_data(inv_data)
    loc_data = make_location_data(id="loc_a", shroud=3)
    g.register_card_data(loc_data)
    g.add_investigator("inv1", inv_data, starting_location="loc_a")
    g.add_location("loc_a", loc_data, clues=1)
    g.register_card_data(make_asset_data(
        id="blasphemous_covenant_lv2", traits=["covenant", "cursed"]))
    inst = CardInstance(
        instance_id="inst_covenant", card_id="blasphemous_covenant_lv2",
        owner_id="inv1", controller_id="inv1",
    )
    g.state.cards_in_play["inst_covenant"] = inst
    g.state.get_investigator("inv1").play_area.append("inst_covenant")
    impl = BlasphemousCovenant("inst_covenant")
    impl.register(g.event_bus, "inst_covenant")
    return g, inst


class TestBlasphemousCovenant:
    def test_curse_treated_as_plus_one(self, game):
        """完整检定：诅咒标记 -2 被替换为 +1（3+1≥3 成功），契约横置。"""
        g, inst = game
        g.chaos_bag.tokens = [ChaosTokenType.CURSE]
        result = g.skill_test_engine.run_test(
            investigator_id="inv1", skill_type=Skill.INTELLECT, difficulty=3,
        )
        assert result.token_modifier == 1
        assert result.success is True
        assert inst.exhausted is True

    def test_no_effect_when_exhausted(self, game):
        g, inst = game
        inst.exhausted = True
        g.chaos_bag.tokens = [ChaosTokenType.CURSE]
        result = g.skill_test_engine.run_test(
            investigator_id="inv1", skill_type=Skill.INTELLECT, difficulty=3,
        )
        assert result.token_modifier == -2

    def test_no_effect_for_investigator_elsewhere(self, game):
        """不在你所在地点的调查员揭示诅咒：不触发。"""
        g, inst = game
        other_data = make_investigator_data(id="inv2", name="Other")
        g.register_card_data(other_data)
        loc_b = make_location_data(id="loc_b")
        g.register_card_data(loc_b)
        g.add_investigator("inv2", other_data, starting_location="loc_b")
        g.add_location("loc_b", loc_b)

        g.chaos_bag.tokens = [ChaosTokenType.CURSE]
        result = g.skill_test_engine.run_test(
            investigator_id="inv2", skill_type=Skill.INTELLECT, difficulty=3,
        )
        assert result.token_modifier == -2
        assert inst.exhausted is False
