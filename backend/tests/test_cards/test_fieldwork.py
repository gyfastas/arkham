"""Tests for Fieldwork (Level 0).

官方：[反应]在你移动到有至少1条线索的地点后，横置实地考察：
本阶段你执行的下一次技能检定+2技能值。
"""

import pytest

from backend.cards.seeker.fieldwork_lv0 import Fieldwork
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import Action, ChaosTokenType, GameEvent, Skill
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_asset_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def game():
    g = Game("test_fieldwork")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data(intellect=3)
    g.register_card_data(inv_data)
    loc_a = make_location_data(id="loc_a", shroud=4, clue_value=0,
                               connections=["loc_b", "loc_c"])
    loc_b = make_location_data(id="loc_b", shroud=4, clue_value=2,
                               connections=["loc_a"])
    loc_c = make_location_data(id="loc_c", shroud=4, clue_value=0,
                               connections=["loc_a"])
    for loc in (loc_a, loc_b, loc_c):
        g.register_card_data(loc)
    g.add_investigator("player", inv_data, starting_location="loc_a")
    g.add_location("loc_a", loc_a, clues=0)
    g.add_location("loc_b", loc_b, clues=2)
    g.add_location("loc_c", loc_c, clues=0)

    g.register_card_data(make_asset_data(
        id="fieldwork_lv0", name="Fieldwork", cost=2, traits=["talent"]))
    inst = CardInstance(
        instance_id="inst_fw", card_id="fieldwork_lv0",
        owner_id="player", controller_id="player",
    )
    g.state.cards_in_play["inst_fw"] = inst
    g.state.get_investigator("player").play_area.append("inst_fw")

    g.card_registry.register_class(Fieldwork)
    g.card_registry.activate_card("fieldwork_lv0", "inst_fw", g.event_bus)
    g.chaos_bag.tokens = [ChaosTokenType.ZERO]
    return g


class TestFieldwork:
    def test_move_to_clue_location_arms_boost(self, game):
        """移动到有线索地点：横置并武装+2；隐蔽4的调查（3智力）因此成功。"""
        inst = game.state.get_card_instance("inst_fw")
        ok = game.action_resolver.perform_action(
            "player", Action.MOVE, destination="loc_b")
        assert ok is True
        assert inst.exhausted is True

        game.action_resolver.perform_action("player", Action.INVESTIGATE)
        inv = game.state.get_investigator("player")
        loc_b = game.state.get_location("loc_b")
        assert inv.clues == 1  # 3+2=5 >= 4 调查成功
        assert loc_b.clues == 1

    def test_move_to_clueless_location_no_trigger(self, game):
        """移动到无线索地点：不横置、不武装。"""
        inst = game.state.get_card_instance("inst_fw")
        game.action_resolver.perform_action(
            "player", Action.MOVE, destination="loc_c")
        assert inst.exhausted is False

        game.action_resolver.perform_action("player", Action.INVESTIGATE)
        inv = game.state.get_investigator("player")
        assert inv.clues == 0  # 3 < 4 调查失败

    def test_boost_applies_once(self, game):
        """+2只对下一次检定生效。"""
        game.action_resolver.perform_action(
            "player", Action.MOVE, destination="loc_b")
        r1 = game.skill_test_engine.run_test(
            investigator_id="player", skill_type=Skill.INTELLECT,
            difficulty=4)
        assert r1.success is True
        sources = r1.extra.get("skill_bonus_sources", [])
        assert any(s["reason"] == "fieldwork_boost" and s["delta"] == 2
                   for s in sources)

        r2 = game.skill_test_engine.run_test(
            investigator_id="player", skill_type=Skill.INTELLECT,
            difficulty=4)
        assert r2.success is False  # 第二次无加值

    def test_expires_at_phase_end(self, game):
        """阶段结束：未用的+2过期。"""
        game.action_resolver.perform_action(
            "player", Action.MOVE, destination="loc_b")
        game.event_bus.emit(EventContext(
            game_state=game.state,
            event=GameEvent.INVESTIGATION_PHASE_ENDS,
        ))
        result = game.skill_test_engine.run_test(
            investigator_id="player", skill_type=Skill.INTELLECT,
            difficulty=4)
        assert result.success is False
