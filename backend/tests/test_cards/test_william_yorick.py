"""Tests for William Yorick investigator ability."""

import pytest
from backend.cards.survivor.william_yorick import WilliamYorick
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import ChaosTokenType, GameEvent, Skill
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_asset_data, make_enemy_data, make_investigator_data,
    make_location_data,
)


@pytest.fixture
def game():
    g = Game("test_yorick")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data(
        id="william_yorick", name="William Yorick", combat=4,
    )
    g.register_card_data(inv_data)
    other_data = make_investigator_data(id="other_inv", name="Other")
    g.register_card_data(other_data)

    loc_data = make_location_data()
    g.register_card_data(loc_data)
    g.register_card_data(make_enemy_data(health=2))
    g.register_card_data(make_asset_data(
        id="leather_coat_lv0", name="Leather Coat", cost=2,
    ))
    g.register_card_data(make_asset_data(
        id="guard_dog_lv0", name="Guard Dog", cost=3,
    ))

    g.add_investigator("yorick", inv_data, deck=["c"] * 10,
                       starting_location="test_location")
    g.add_investigator("other", other_data, deck=["c"] * 10,
                       starting_location="test_location")
    g.add_location("test_location", loc_data, clues=3)
    return g


@pytest.fixture
def impl(game):
    impl = WilliamYorick("test_instance")
    impl.register(game.event_bus, "test_instance")
    return impl


def _emit(game, event, **kwargs):
    ctx = EventContext(game_state=game.state, event=event, **kwargs)
    game.event_bus.emit(ctx)
    return ctx


def _add_enemy(game, instance_id):
    game.state.cards_in_play[instance_id] = CardInstance(
        instance_id=instance_id, card_id="test_enemy",
        owner_id="scenario", controller_id="scenario",
    )
    return game.state.cards_in_play[instance_id]


def _defeat(game, instance_id, defeater="yorick"):
    """约里克（或指定者）以伤害击败敌人。"""
    return game.damage_engine.deal_damage_to_enemy(
        instance_id, 5, investigator_id=defeater,
    )


class TestPlayAssetOnDefeat:
    def test_defeat_enemy_plays_asset_from_discard(self, game, impl):
        """击败敌人后：支付费用从弃牌堆打出一张支援卡。"""
        inv = game.state.get_investigator("yorick")
        inv.resources = 5
        inv.discard.append("leather_coat_lv0")
        _add_enemy(game, "enemy_1")

        assert _defeat(game, "enemy_1")
        assert inv.resources == 3
        assert "leather_coat_lv0" not in inv.discard
        assert len(inv.play_area) == 1
        inst = game.state.get_card_instance(inv.play_area[0])
        assert inst.card_id == "leather_coat_lv0"
        assert inst.controller_id == "yorick"

    def test_limit_once_per_round(self, game, impl):
        """每轮限1次；下一轮重置。"""
        inv = game.state.get_investigator("yorick")
        inv.discard.extend(["leather_coat_lv0", "guard_dog_lv0"])
        _add_enemy(game, "enemy_1")
        _add_enemy(game, "enemy_2")
        _add_enemy(game, "enemy_3")

        _defeat(game, "enemy_1")
        assert len(inv.play_area) == 1
        # 本轮第二次击败：不再触发
        _defeat(game, "enemy_2")
        assert len(inv.play_area) == 1

        _emit(game, GameEvent.ROUND_BEGINS)
        _defeat(game, "enemy_3")
        assert len(inv.play_area) == 2
        assert inv.resources == 5 - 2 - 3

    def test_no_trigger_when_unaffordable(self, game, impl):
        """弃牌堆支援费用不可负担时不触发，且不消耗限次。"""
        inv = game.state.get_investigator("yorick")
        inv.resources = 1
        inv.discard.append("leather_coat_lv0")
        _add_enemy(game, "enemy_1")
        _add_enemy(game, "enemy_2")

        _defeat(game, "enemy_1")
        assert inv.play_area == []
        assert "leather_coat_lv0" in inv.discard

        # 限次未消耗：补足资源后再次击败可打出
        inv.resources = 5
        _defeat(game, "enemy_2")
        assert len(inv.play_area) == 1

    def test_no_trigger_for_other_investigators_defeat(self, game, impl):
        """其他调查员击败敌人不触发。"""
        inv = game.state.get_investigator("yorick")
        inv.discard.append("leather_coat_lv0")
        _add_enemy(game, "enemy_1")

        _defeat(game, "enemy_1", defeater="other")
        assert inv.play_area == []
        assert "leather_coat_lv0" in inv.discard

    def test_var_override_selects_asset(self, game, impl):
        """可用 scenario.vars["yorick_asset_choice_{inv}"] 指定打出的支援。"""
        inv = game.state.get_investigator("yorick")
        inv.discard.extend(["leather_coat_lv0", "guard_dog_lv0"])
        _add_enemy(game, "enemy_1")

        game.state.scenario.vars["yorick_asset_choice_yorick"] = "guard_dog_lv0"
        _defeat(game, "enemy_1")
        inst = game.state.get_card_instance(inv.play_area[0])
        assert inst.card_id == "guard_dog_lv0"
        assert "leather_coat_lv0" in inv.discard


class TestElderSign:
    def _run_elder_sign_test(self, game, difficulty):
        game.chaos_bag.tokens = [ChaosTokenType.ELDER_SIGN]
        return game.skill_test_engine.run_test(
            investigator_id="yorick",
            skill_type=Skill.COMBAT,
            difficulty=difficulty,
        )

    def test_elder_sign_success_returns_discard_card(self, game, impl):
        """远古印记：+2；检定成功则将弃牌堆1张卡返回手牌。"""
        inv = game.state.get_investigator("yorick")
        inv.discard.extend(["leather_coat_lv0", "guard_dog_lv0"])

        result = self._run_elder_sign_test(game, difficulty=1)
        assert result.token_modifier == 2
        assert result.success
        # 弃牌堆顶的卡返回手牌
        assert "guard_dog_lv0" in inv.hand
        assert inv.discard == ["leather_coat_lv0"]

    def test_elder_sign_failure_returns_nothing(self, game, impl):
        """远古印记：检定失败则不返回卡牌。"""
        inv = game.state.get_investigator("yorick")
        inv.discard.append("guard_dog_lv0")

        result = self._run_elder_sign_test(game, difficulty=99)
        assert result.token_modifier == 2
        assert not result.success
        assert inv.discard == ["guard_dog_lv0"]
        assert "guard_dog_lv0" not in inv.hand

    def test_elder_sign_only_for_yorick(self, game, impl):
        """其他调查员抽远古印记不享受约里克的印记效果。"""
        game.chaos_bag.tokens = [ChaosTokenType.ELDER_SIGN]
        result = game.skill_test_engine.run_test(
            investigator_id="other", skill_type=Skill.COMBAT, difficulty=1,
        )
        assert result.token_modifier == 0
