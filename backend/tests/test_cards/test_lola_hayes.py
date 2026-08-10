"""Tests for Lola Hayes investigator ability."""

import pytest
from backend.cards.neutral.crisis_of_identity_lv0 import (
    role_key as crisis_role_key,
)
from backend.cards.neutral.lola_hayes import LolaHayes, role_key
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import (
    ChaosTokenType, GameEvent, PlayerClass, Skill,
)
from backend.tests.conftest import (
    make_asset_data, make_investigator_data, make_location_data,
)


def _make_game():
    g = Game("test_lola")
    g.chaos_bag.seed(42)
    inv_data = make_investigator_data(id="lola_hayes", name="Lola Hayes")
    g.register_card_data(inv_data)
    loc_data = make_location_data()
    g.register_card_data(loc_data)
    g.add_investigator("lola", inv_data, deck=["c"] * 10,
                       starting_location="test_location")
    g.add_location("test_location", loc_data, clues=3)
    return g


@pytest.fixture
def game():
    return _make_game()


@pytest.fixture
def impl(game):
    impl = LolaHayes("test_instance")
    impl.register(game.event_bus, "test_instance")
    return impl


def _emit(game, event, **kwargs):
    ctx = EventContext(game_state=game.state, event=event, **kwargs)
    game.event_bus.emit(ctx)
    return ctx


class TestRoleKeyConvention:
    def test_role_key_matches_crisis_of_identity(self):
        """role 存储键与 crisis_of_identity / improvisation 的既定约定一致。"""
        assert role_key("lola") == crisis_role_key("lola") == "role_lola"


class TestInitialRole:
    def test_setup_offers_initial_role_choice(self):
        """开局强制能力：抽取起始手牌后设置初始角色 pending_choice。"""
        g = _make_game()
        g.setup()

        pending = g.state.scenario.vars.get("pending_choice")
        assert pending is not None
        assert pending["kind"] == "lola_hayes_initial_role"
        assert pending["investigator_id"] == "lola"
        assert {o["id"] for o in pending["options"]} == {
            "survivor", "guardian", "seeker", "rogue", "mystic", "neutral",
        }
        # 起始手牌正常抽取
        assert len(g.state.get_investigator("lola").hand) == 5

    def test_resolve_initial_role(self):
        """解析初始角色选择：写入角色并清除 pending_choice。"""
        g = _make_game()
        g.setup()
        impl = g.card_registry.active_instances["investigator_lola"]

        # 解析前为缺省中立角色
        assert impl.get_role(g.state, "lola") == "neutral"

        assert impl.resolve_role_choice(g.state, "lola", "rogue")
        assert "pending_choice" not in g.state.scenario.vars
        assert g.state.scenario.vars["role_lola"] == "rogue"

        # 非法角色被拒绝
        assert not impl.resolve_role_choice(g.state, "lola", "druid")


class TestSwitchRole:
    def test_switch_role_once_per_round(self, game, impl):
        """[fast]：切换角色，每轮限1次；下一轮重置。"""
        assert impl.switch_role(game.state, "lola", "mystic")
        assert game.state.scenario.vars["role_lola"] == "mystic"

        # 本轮第二次：失败
        assert not impl.switch_role(game.state, "lola", "seeker")
        assert game.state.scenario.vars["role_lola"] == "mystic"

        _emit(game, GameEvent.ROUND_BEGINS)
        assert impl.switch_role(game.state, "lola", "seeker")
        assert game.state.scenario.vars["role_lola"] == "seeker"

    def test_switch_role_rejects_invalid_role(self, game, impl):
        """非法角色 / 非萝拉调查员不可切换。"""
        assert not impl.switch_role(game.state, "lola", "druid")
        assert "role_lola" not in game.state.scenario.vars


class TestRoleRestriction:
    def test_can_play_card_matches_role(self, game, impl):
        """只能打出/投入/触发中立卡或当前角色卡（供会话层接线）。"""
        game.register_card_data(make_asset_data(
            id="machete_lv0", card_class=PlayerClass.GUARDIAN,
        ))
        game.register_card_data(make_asset_data(
            id="lockpicks_lv1", card_class=PlayerClass.ROGUE,
        ))
        game.register_card_data(make_asset_data(
            id="knife_lv0", card_class=PlayerClass.NEUTRAL,
        ))

        impl.resolve_role_choice(game.state, "lola", "guardian")
        assert impl.can_play_card(game.state, "lola", "machete_lv0")
        assert impl.can_play_card(game.state, "lola", "knife_lv0")
        assert not impl.can_play_card(game.state, "lola", "lockpicks_lv1")

        # 切换为中立角色后：只有中立卡可用
        impl.resolve_role_choice(game.state, "lola", "neutral")
        assert not impl.can_play_card(game.state, "lola", "machete_lv0")
        assert impl.can_play_card(game.state, "lola", "knife_lv0")


class TestElderSign:
    def test_elder_sign_plus2_and_role_choice(self, game, impl):
        """远古印记：+2，并设置可切换角色的 pending_choice。"""
        game.chaos_bag.tokens = [ChaosTokenType.ELDER_SIGN]
        result = game.skill_test_engine.run_test(
            investigator_id="lola", skill_type=Skill.COMBAT, difficulty=99,
        )
        assert result.token_modifier == 2

        pending = game.state.scenario.vars.get("pending_choice")
        assert pending is not None
        assert pending["kind"] == "lola_hayes_elder_sign_role"
        assert "decline" in {o["id"] for o in pending["options"]}

        # 解析：切换角色（不占每轮限次）
        assert impl.resolve_role_choice(game.state, "lola", "seeker")
        assert game.state.scenario.vars["role_lola"] == "seeker"
        assert "pending_choice" not in game.state.scenario.vars
        assert impl.switch_role(game.state, "lola", "mystic")

    def test_elder_sign_decline_keeps_role(self, game, impl):
        """远古印记的角色切换可放弃：角色保持，pending_choice 清除。"""
        impl.resolve_role_choice(game.state, "lola", "guardian")

        game.chaos_bag.tokens = [ChaosTokenType.ELDER_SIGN]
        game.skill_test_engine.run_test(
            investigator_id="lola", skill_type=Skill.COMBAT, difficulty=99,
        )
        assert impl.decline_role_choice(game.state, "lola")
        assert game.state.scenario.vars["role_lola"] == "guardian"
        assert "pending_choice" not in game.state.scenario.vars

    def test_elder_sign_only_for_lola(self, game, impl):
        """其他调查员抽远古印记不享受萝拉的印记效果。"""
        other_data = make_investigator_data(id="other_inv", name="Other")
        game.register_card_data(other_data)
        game.add_investigator("other", other_data, deck=["c"] * 5,
                              starting_location="test_location")

        game.chaos_bag.tokens = [ChaosTokenType.ELDER_SIGN]
        result = game.skill_test_engine.run_test(
            investigator_id="other", skill_type=Skill.COMBAT, difficulty=99,
        )
        assert result.token_modifier == 0
        assert "pending_choice" not in game.state.scenario.vars
