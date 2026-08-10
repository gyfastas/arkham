"""Tests for Tommy Muldoon investigator ability and elder sign."""

import pytest

from backend.cards.guardian.tommy_muldoon import TommyMuldoon
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import ChaosTokenType, GameEvent
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_asset_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def game():
    g = Game("test_tommy")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data(id="tommy_muldoon", name="Tommy Muldoon")
    g.register_card_data(inv_data)

    loc_data = make_location_data()
    g.register_card_data(loc_data)

    ally_data = make_asset_data(id="test_ally", name="Test Ally", health=2, sanity=2)
    g.register_card_data(ally_data)

    deck = ["card_a", "card_b", "card_c", "card_d", "card_e"] * 3
    g.add_investigator("tommy", inv_data, deck=deck, starting_location="test_location")
    g.add_location("test_location", loc_data, clues=3)
    return g


@pytest.fixture
def impl(game):
    impl = TommyMuldoon("test_instance")
    impl.register(game.event_bus, "test_instance")
    return impl


def _add_ally(game, instance_id="ally_1", damage=0, horror=0, owner="tommy"):
    ally = CardInstance(
        instance_id=instance_id, card_id="test_ally",
        owner_id=owner, controller_id=owner, damage=damage, horror=horror,
    )
    game.state.cards_in_play[instance_id] = ally
    game.state.get_investigator(owner).play_area.append(instance_id)
    return ally


def _emit(game, event, **kwargs):
    ctx = EventContext(game_state=game.state, event=event, **kwargs)
    game.event_bus.emit(ctx)
    return ctx


class TestTommyMuldoonReaction:
    def test_defeated_asset_grants_resources_and_shuffles_into_deck(self, game, impl):
        """支援被击败：获得其上伤害+恐惧总数的资源，并混洗入牌堆（走引擎伤害流程）。"""
        ally = _add_ally(game, damage=1, horror=1)  # health=2
        inv = game.state.get_investigator("tommy")
        inv.resources = 0
        deck_before = list(inv.deck)

        # 引擎分配1点伤害到盟友 → 盟友伤害达2被击败
        game.damage_engine.deal_damage(
            "tommy", damage=1, damage_assignment={"ally_1": 1},
        )

        # X = 2伤害 + 1恐惧 = 3
        assert inv.resources == 3
        # 不进入弃牌堆，而是混洗入牌堆
        assert "test_ally" not in inv.discard
        assert "test_ally" in inv.deck
        assert len(inv.deck) == len(deck_before) + 1
        assert "ally_1" not in game.state.cards_in_play
        assert "ally_1" not in inv.play_area

    def test_no_trigger_for_other_investigators_asset(self, game, impl):
        """其他调查员的支援被击败不触发。"""
        other_data = make_investigator_data(id="other_inv", name="Other")
        game.register_card_data(other_data)
        game.add_investigator("other", other_data, deck=[], starting_location="test_location")
        _add_ally(game, instance_id="ally_2", damage=1, owner="other")
        inv = game.state.get_investigator("tommy")
        inv.resources = 0

        game.damage_engine.deal_damage(
            "other", damage=1, damage_assignment={"ally_2": 1},
        )
        assert inv.resources == 0
        assert "test_ally" in game.state.get_investigator("other").discard

    def test_zero_damage_horror_asset_still_shuffles(self, game, impl):
        """无既有伤害/恐惧的支援被击败：X=击败时其上伤害（致命伤害计入），仍混洗入牌堆。"""
        _add_ally(game, damage=0, horror=0)
        inv = game.state.get_investigator("tommy")
        inv.resources = 1

        game.damage_engine.deal_damage(
            "tommy", damage=2, damage_assignment={"ally_1": 2},
        )
        # 击败时支援上有2点伤害（致命伤害本身）→ X=2
        assert inv.resources == 3
        assert "test_ally" in inv.deck
        assert "test_ally" not in inv.discard


class TestTommyMuldoonElderSign:
    def test_elder_sign_plus_two_and_pending_choice(self, game, impl):
        """远古印记：+2，并提供伤害/恐惧移动选择。"""
        ally = _add_ally(game, damage=1)
        game.state.get_investigator("tommy").damage = 1

        ctx = _emit(
            game, GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="tommy", chaos_token=ChaosTokenType.ELDER_SIGN,
        )
        assert ctx.amount == 2
        pending = game.state.scenario.vars.get("pending_choice", {})
        assert pending.get("kind") == "tommy_muldoon_transfer"
        option_ids = [o["id"] for o in pending["options"]]
        assert "to:ally_1" in option_ids
        assert "from:ally_1" in option_ids
        assert ally.damage == 1  # 未结算前不变

    def test_transfer_to_asset(self, game, impl):
        """将托米身上的伤害/恐惧移到支援上（合计最多2点）。"""
        ally = _add_ally(game)
        inv = game.state.get_investigator("tommy")
        inv.damage = 2
        inv.horror = 1

        _emit(
            game, GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="tommy", chaos_token=ChaosTokenType.ELDER_SIGN,
        )
        assert impl.resolve_transfer(
            game.state, "tommy", "ally_1", damage=1, horror=1, to_asset=True,
        )
        assert (inv.damage, inv.horror) == (1, 0)
        assert (ally.damage, ally.horror) == (1, 1)

    def test_transfer_from_asset(self, game, impl):
        """将支援上的伤害移到托米身上；超出可用部分被截断。"""
        ally = _add_ally(game, damage=1, horror=0)
        inv = game.state.get_investigator("tommy")
        inv.damage = 0

        _emit(
            game, GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="tommy", chaos_token=ChaosTokenType.ELDER_SIGN,
        )
        # 请求2点但支援上只有1点伤害 → 实际移动1点
        assert impl.resolve_transfer(
            game.state, "tommy", "ally_1", damage=2, to_asset=False,
        )
        assert ally.damage == 0
        assert inv.damage == 1

    def test_preset_transfer_applied_immediately(self, game, impl):
        """scenario.vars 预设在远古印记结算时立即生效（一次性）。"""
        ally = _add_ally(game)
        inv = game.state.get_investigator("tommy")
        inv.damage = 2

        game.state.scenario.vars["tommy_muldoon_transfer"] = {
            "instance_id": "ally_1", "damage": 2, "horror": 0, "to_asset": True,
        }
        ctx = _emit(
            game, GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="tommy", chaos_token=ChaosTokenType.ELDER_SIGN,
        )
        assert ctx.amount == 2
        assert inv.damage == 0
        assert ally.damage == 2
        assert game.state.scenario.vars.get("pending_choice") is None
        assert "tommy_muldoon_transfer" not in game.state.scenario.vars
