"""Tests for Silas Marsh investigator ability."""

import pytest
from backend.cards.survivor.silas_marsh import SilasMarsh
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import ChaosTokenType, GameEvent, Skill
from backend.tests.conftest import (
    make_investigator_data, make_location_data, make_skill_data,
)


@pytest.fixture
def game():
    g = Game("test_silas")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data(
        id="silas_marsh", name="Silas Marsh", intellect=3)
    g.register_card_data(inv_data)

    loc_data = make_location_data()
    g.register_card_data(loc_data)

    g.register_card_data(make_skill_data(
        id="skill_icons", name="Icon Skill",
        skill_icons={"intellect": 2}))
    g.register_card_data(make_skill_data(
        id="skill_wild", name="Wild Skill", skill_icons={"wild": 1}))
    g.register_card_data(make_skill_data(
        id="skill_off", name="Off Skill", skill_icons={"combat": 2}))

    deck = ["card_a", "card_b", "card_c", "card_d", "card_e"] * 3
    g.add_investigator("silas", inv_data, deck=deck, starting_location="test_location")
    g.add_location("test_location", loc_data, clues=3)

    return g


@pytest.fixture
def impl(game):
    impl = SilasMarsh("test_instance")
    impl.register(game.event_bus, "test_instance")
    return impl


def _emit(game, event, **kwargs):
    ctx = EventContext(game_state=game.state, event=event, **kwargs)
    game.event_bus.emit(ctx)
    return ctx


class TestSilasReturnCommittedSkill:
    def test_returned_skill_goes_to_hand_not_discard(self, game, impl):
        """揭示标记后：投入的技能卡返回手牌而非弃置，其图标被扣回。"""
        inv = game.state.get_investigator("silas")
        inv.hand = ["skill_icons"]
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]

        # 3智力+2图标 vs 难度4：图标被扣回后 3 vs 4 失败
        result = game.skill_test_engine.run_test(
            investigator_id="silas",
            skill_type=Skill.INTELLECT,
            difficulty=4,
            committed_card_ids=["skill_icons"],
        )
        assert not result.success  # 图标扣回，3 < 4
        assert result.token_modifier == -2  # 0（标记）- 2（扣回图标）
        assert "skill_icons" in inv.hand
        assert "skill_icons" not in inv.discard

    def test_prefers_skill_with_fewest_matching_icons(self, game, impl):
        """自动选择匹配图标最少的投入技能卡（off-skill 优先）。"""
        inv = game.state.get_investigator("silas")
        inv.hand = ["skill_icons", "skill_off"]
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]

        result = game.skill_test_engine.run_test(
            investigator_id="silas",
            skill_type=Skill.INTELLECT,
            difficulty=1,
            committed_card_ids=["skill_icons", "skill_off"],
        )
        # combat 图标对智力检定无贡献（0匹配），被优先返回
        assert "skill_off" in inv.hand
        assert "skill_icons" in inv.discard
        assert result.token_modifier == 0  # 无需扣回

    def test_once_per_round(self, game, impl):
        """每轮限1次；新一轮重置。"""
        inv = game.state.get_investigator("silas")
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]

        inv.hand = ["skill_icons"]
        game.skill_test_engine.run_test(
            investigator_id="silas", skill_type=Skill.INTELLECT,
            difficulty=1, committed_card_ids=["skill_icons"])
        assert "skill_icons" in inv.hand

        # 同轮第二次：不再返回（技能正常进弃牌堆）
        game.skill_test_engine.run_test(
            investigator_id="silas", skill_type=Skill.INTELLECT,
            difficulty=1, committed_card_ids=["skill_icons"])
        assert "skill_icons" in inv.discard

        # 新一轮：重置
        _emit(game, GameEvent.ROUND_BEGINS)
        inv.hand.append("skill_icons")
        inv.discard.remove("skill_icons")
        game.skill_test_engine.run_test(
            investigator_id="silas", skill_type=Skill.INTELLECT,
            difficulty=1, committed_card_ids=["skill_icons"])
        assert "skill_icons" in inv.hand

    def test_no_committed_skill_no_trigger(self, game, impl):
        """未投入技能卡时不触发（每轮限次不消耗）。"""
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]
        result = game.skill_test_engine.run_test(
            investigator_id="silas", skill_type=Skill.INTELLECT, difficulty=1)
        assert result.success
        assert impl._used_this_round is False


class TestSilasElderSign:
    def test_commit_skill_from_discard_and_return(self, game, impl):
        """远古印记：+0，自动投入弃牌堆顶技能卡（图标生效），检定后回手。"""
        inv = game.state.get_investigator("silas")
        inv.discard = ["skill_icons"]
        game.chaos_bag.tokens = [ChaosTokenType.ELDER_SIGN]

        # 3智力+2图标（弃牌堆投入）vs 难度4：成功
        result = game.skill_test_engine.run_test(
            investigator_id="silas",
            skill_type=Skill.INTELLECT,
            difficulty=4,
        )
        assert result.success
        assert result.token == ChaosTokenType.ELDER_SIGN
        assert result.token_modifier == 2  # 来自弃牌堆技能卡的图标
        assert "skill_icons" in inv.hand
        assert "skill_icons" not in inv.discard

    def test_no_skill_in_discard(self, game, impl):
        """弃牌堆无技能卡：仅 +0。"""
        game.chaos_bag.tokens = [ChaosTokenType.ELDER_SIGN]
        result = game.skill_test_engine.run_test(
            investigator_id="silas", skill_type=Skill.INTELLECT, difficulty=3)
        assert result.success
        assert result.token_modifier == 0

    def test_elder_sign_other_investigator_unaffected(self, game, impl):
        """其他调查员抽到远古印记不触发 Silas 效果。"""
        other_data = make_investigator_data(id="other_inv", name="Other")
        game.register_card_data(other_data)
        game.add_investigator("other", other_data, deck=[],
                              starting_location="test_location")
        other = game.state.get_investigator("other")
        other.discard = ["skill_icons"]
        game.chaos_bag.tokens = [ChaosTokenType.ELDER_SIGN]

        result = game.skill_test_engine.run_test(
            investigator_id="other", skill_type=Skill.INTELLECT, difficulty=3)
        assert result.token_modifier == 0
        assert "skill_icons" in other.discard
