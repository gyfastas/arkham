"""Tests for Minh Thi Phan investigator ability."""

import pytest
from backend.cards.seeker.minh_thi_phan import MinhThiPhan
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import ChaosTokenType, GameEvent, Skill
from backend.tests.conftest import (
    make_event_data, make_investigator_data, make_location_data,
    make_skill_data,
)


@pytest.fixture
def game():
    g = Game("test_minh")
    g.chaos_bag.seed(42)

    minh_data = make_investigator_data(
        id="minh_thi_phan", name="Minh Thi Phan", willpower=4,
    )
    g.register_card_data(minh_data)
    other_data = make_investigator_data(id="roland_banks", name="Roland Banks")
    g.register_card_data(other_data)

    loc_data = make_location_data()
    g.register_card_data(loc_data)
    other_loc = make_location_data(id="other_location", name="Other Location")
    g.register_card_data(other_loc)

    g.add_investigator("minh", minh_data, deck=["c"] * 10,
                       starting_location="test_location")
    g.add_investigator("roland", other_data, deck=["c"] * 10,
                       starting_location="test_location")
    g.add_location("test_location", loc_data, clues=3)
    g.add_location("other_location", other_loc, clues=0)
    return g


@pytest.fixture
def impl(game):
    impl = MinhThiPhan("test_instance")
    impl.register(game.event_bus, "test_instance")
    return impl


def _emit(game, event, **kwargs):
    ctx = EventContext(game_state=game.state, event=event, **kwargs)
    game.event_bus.emit(ctx)
    return ctx


def _commit(game, investigator_id, cards, amount=0):
    return _emit(
        game, GameEvent.SKILL_TEST_COMMIT,
        investigator_id=investigator_id, skill_type=Skill.INTELLECT,
        committed_cards=list(cards), amount=amount,
    )


class TestGrantWildIcon:
    def test_commit_at_minhs_location_gains_wild_icon(self, game, impl):
        """潘明所在地点的调查员投入卡牌后：本次检定总图标+1（wild 等效）。"""
        ctx = _commit(game, "roland", ["dynamite_blast_lv0"], amount=0)
        assert ctx.amount == 1
        assert ctx.extra["minh_wild_icon_card"] == "dynamite_blast_lv0"

    def test_limit_once_per_investigator_per_round(self, game, impl):
        """每位调查员每轮限1次；潘明自己有独立的限次；下一轮重置。"""
        assert _commit(game, "roland", ["card_x"]).amount == 1
        # 罗兰本轮第二次投入：不再触发
        assert _commit(game, "roland", ["card_y"]).amount == 0
        # 潘明本轮首次投入：仍可触发（限次按调查员计）
        assert _commit(game, "minh", ["card_z"]).amount == 1
        assert _commit(game, "minh", ["card_w"]).amount == 0

        _emit(game, GameEvent.ROUND_BEGINS)
        assert _commit(game, "roland", ["card_x"]).amount == 1

    def test_no_grant_at_other_location(self, game, impl):
        """不在潘明所在地点的调查员投入不触发。"""
        roland = game.state.get_investigator("roland")
        roland.location_id = "other_location"
        assert _commit(game, "roland", ["card_x"]).amount == 0

    def test_no_grant_without_committed_cards(self, game, impl):
        """未投入卡牌的检定不触发。"""
        assert _commit(game, "roland", []).amount == 0


class TestElderSign:
    def _run_elder_sign_test(self, game, committed):
        game.chaos_bag.tokens = [ChaosTokenType.ELDER_SIGN]
        minh = game.state.get_investigator("minh")
        minh.hand.extend(committed)
        return game.skill_test_engine.run_test(
            investigator_id="minh",
            skill_type=Skill.WILLPOWER,
            difficulty=1,
            committed_card_ids=committed,
            effect_card_ids=[],
        )

    def test_elder_sign_returns_committed_skill_card(self, game, impl):
        """远古印记：+1；检定结束后投入的技能卡返回手牌。"""
        game.register_card_data(make_skill_data(
            id="guts_lv0", skill_icons={"willpower": 2},
        ))
        result = self._run_elder_sign_test(game, ["guts_lv0"])

        # 4（意志）+2（图标）+1（潘明能力 wild）+1（远古印记）= 8
        assert result.token_modifier == 1
        assert result.success

        minh = game.state.get_investigator("minh")
        assert "guts_lv0" in minh.hand
        assert "guts_lv0" not in minh.discard

    def test_elder_sign_does_not_return_non_skill_card(self, game, impl):
        """远古印记只回手技能卡：投入的事件卡照常弃置。"""
        game.register_card_data(make_event_data(id="dodge_lv0"))
        result = self._run_elder_sign_test(game, ["dodge_lv0"])
        assert result.token_modifier == 1

        minh = game.state.get_investigator("minh")
        assert "dodge_lv0" in minh.discard
        assert "dodge_lv0" not in minh.hand

    def test_committed_skill_discarded_without_elder_sign(self, game, impl):
        """未抽远古印记时，投入的技能卡正常进入弃牌堆。"""
        game.register_card_data(make_skill_data(
            id="guts_lv0", skill_icons={"willpower": 2},
        ))
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]
        minh = game.state.get_investigator("minh")
        minh.hand.append("guts_lv0")
        game.skill_test_engine.run_test(
            investigator_id="minh",
            skill_type=Skill.WILLPOWER,
            difficulty=1,
            committed_card_ids=["guts_lv0"],
            effect_card_ids=[],
        )
        assert "guts_lv0" in minh.discard
        assert "guts_lv0" not in minh.hand

    def test_elder_sign_only_for_minh(self, game, impl):
        """其他调查员抽远古印记不享受潘明的印记效果。"""
        game.register_card_data(make_skill_data(
            id="guts_lv0", skill_icons={"intellect": 1},
        ))
        game.chaos_bag.tokens = [ChaosTokenType.ELDER_SIGN]
        roland = game.state.get_investigator("roland")
        roland.hand.append("guts_lv0")
        result = game.skill_test_engine.run_test(
            investigator_id="roland",
            skill_type=Skill.INTELLECT,
            difficulty=1,
            committed_card_ids=["guts_lv0"],
            effect_card_ids=[],
        )
        assert result.token_modifier == 0
        assert "guts_lv0" in roland.discard
