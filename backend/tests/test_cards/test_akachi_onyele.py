"""Tests for Akachi Onyele investigator ability."""

import pytest
from backend.cards.mystic.akachi_onyele import AkachiOnyele
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import Action, ChaosTokenType, GameEvent, Skill
from backend.tests.conftest import (
    make_asset_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def game():
    g = Game("test_akachi")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data(
        id="akachi_onyele", name="Akachi Onyele", willpower=5,
    )
    g.register_card_data(inv_data)
    other_data = make_investigator_data(id="other_inv", name="Other")
    g.register_card_data(other_data)

    loc_data = make_location_data()
    g.register_card_data(loc_data)

    g.register_card_data(make_asset_data(
        id="shrivelling_lv0", name="Shrivelling", cost=3,
        uses={"charges": 4},
    ))
    g.register_card_data(make_asset_data(
        id="flashlight_lv0", name="Flashlight", cost=2,
        uses={"supply": 3},
    ))

    g.add_investigator("akachi", inv_data, deck=["c"] * 10,
                       starting_location="test_location")
    g.add_investigator("other", other_data, deck=["c"] * 10,
                       starting_location="test_location")
    g.add_location("test_location", loc_data, clues=3)
    return g


@pytest.fixture
def impl(game):
    impl = AkachiOnyele("test_instance")
    impl.register(game.event_bus, "test_instance")
    return impl


def _emit(game, event, **kwargs):
    ctx = EventContext(game_state=game.state, event=event, **kwargs)
    game.event_bus.emit(ctx)
    return ctx


def _play(game, investigator_id, card_id):
    inv = game.state.get_investigator(investigator_id)
    inv.hand.append(card_id)
    assert game.action_resolver.perform_action(
        investigator_id, Action.PLAY, card_id=card_id,
    )
    return game.state.get_card_instance(inv.play_area[-1])


class TestBonusChargeOnEnter:
    def test_charges_asset_enters_with_bonus_charge(self, game, impl):
        """带"使用(充能)"的支援卡入场时额外+1充能。"""
        inst = _play(game, "akachi", "shrivelling_lv0")
        assert inst.uses["charges"] == 5

    def test_non_charges_uses_unaffected(self, game, impl):
        """使用(补给)等其他用途类型不加充能。"""
        inst = _play(game, "akachi", "flashlight_lv0")
        assert inst.uses == {"supply": 3}

    def test_no_bonus_for_other_investigators(self, game, impl):
        """其他调查员的充能支援入场不加成。"""
        inst = _play(game, "other", "shrivelling_lv0")
        assert inst.uses["charges"] == 4


class TestElderSign:
    def test_elder_sign_plus1_and_adds_charge(self, game, impl):
        """远古印记：+1，并给你控制的一张充能支援+1充能。"""
        inst = _play(game, "akachi", "shrivelling_lv0")
        assert inst.uses["charges"] == 5  # 入场加成

        game.chaos_bag.tokens = [ChaosTokenType.ELDER_SIGN]
        result = game.skill_test_engine.run_test(
            investigator_id="akachi", skill_type=Skill.WILLPOWER, difficulty=99,
        )
        assert result.token_modifier == 1
        assert inst.uses["charges"] == 6

    def test_elder_sign_prefers_var_override_target(self, game, impl):
        """可用 scenario.vars["akachi_onyele_charge_target"] 指定充能目标。"""
        game.state.get_investigator("akachi").resources = 10
        first = _play(game, "akachi", "shrivelling_lv0")
        second = _play(game, "akachi", "shrivelling_lv0")

        game.state.scenario.vars["akachi_onyele_charge_target"] = second.instance_id
        game.chaos_bag.tokens = [ChaosTokenType.ELDER_SIGN]
        game.skill_test_engine.run_test(
            investigator_id="akachi", skill_type=Skill.WILLPOWER, difficulty=99,
        )
        assert first.uses["charges"] == 5
        assert second.uses["charges"] == 6

    def test_elder_sign_plus1_only_without_charges_asset(self, game, impl):
        """没有充能支援时远古印记只有 +1。"""
        _play(game, "akachi", "flashlight_lv0")

        game.chaos_bag.tokens = [ChaosTokenType.ELDER_SIGN]
        result = game.skill_test_engine.run_test(
            investigator_id="akachi", skill_type=Skill.WILLPOWER, difficulty=99,
        )
        assert result.token_modifier == 1
        inst = game.state.get_card_instance(
            game.state.get_investigator("akachi").play_area[-1]
        )
        assert inst.uses == {"supply": 3}

    def test_elder_sign_only_for_akachi(self, game, impl):
        """其他调查员抽远古印记不享受阿喀琦的印记效果。"""
        inst = _play(game, "other", "shrivelling_lv0")

        game.chaos_bag.tokens = [ChaosTokenType.ELDER_SIGN]
        result = game.skill_test_engine.run_test(
            investigator_id="other", skill_type=Skill.WILLPOWER, difficulty=99,
        )
        assert result.token_modifier == 0
        assert inst.uses["charges"] == 4
