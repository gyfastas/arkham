"""Tests for Hope (Level 0)."""

import pytest
from backend.cards.survivor.hope_lv0 import Hope
from backend.models.enums import (
    ChaosTokenType, GameEvent, PlayerClass, SlotType,
)
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_asset_data, make_enemy_data, make_investigator_data,
    make_location_data,
)
from backend.engine.event_bus import EventContext
from backend.engine.game import Game


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)
    inv_data = make_investigator_data(agility=3)
    g.register_card_data(inv_data)
    loc = make_location_data()
    g.register_card_data(loc)
    for cid in ("hope_lv0", "zeal_lv0", "augur_lv0"):
        g.register_card_data(make_asset_data(
            id=cid, name=cid, cost=1, card_class=PlayerClass.SURVIVOR,
            traits=["ally", "creature", "dreamlands"]))
    g.register_card_data(make_enemy_data(fight=3, health=5, evade=4))
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)
    g.card_registry.register_class(Hope)
    return g


def _equip_hope(game):
    inv = game.state.get_investigator("inv1")
    iid = game.state.next_instance_id()
    game.state.cards_in_play[iid] = CardInstance(
        instance_id=iid, card_id="hope_lv0",
        owner_id="inv1", controller_id="inv1",
    )
    inv.play_area.append(iid)
    game.card_registry.activate_card(
        "hope_lv0", iid, game.event_bus, chaos_bag=game.chaos_bag)
    return iid


def _spawn_enemy(game):
    game.state.cards_in_play["enemy_1"] = CardInstance(
        instance_id="enemy_1", card_id="test_enemy",
        owner_id="scenario", controller_id="scenario",
    )
    game.state.get_investigator("inv1").threat_area.append("enemy_1")
    return game.state.cards_in_play["enemy_1"]


class TestHope:
    def test_card_registered(self, game):
        assert "hope_lv0" in game.card_registry.registered_cards

    def test_enters_play_discards_zeal_and_augur(self, game):
        """霍普入场后：弃置 Zeal 与 Augur。"""
        hope_id = _equip_hope(game)
        inv = game.state.get_investigator("inv1")
        for cid in ("zeal_lv0", "augur_lv0"):
            iid = game.state.next_instance_id()
            game.state.cards_in_play[iid] = CardInstance(
                instance_id=iid, card_id=cid,
                owner_id="inv1", controller_id="inv1",
            )
            inv.play_area.append(iid)

        game.event_bus.emit(EventContext(
            game_state=game.state, event=GameEvent.CARD_ENTERS_PLAY,
            investigator_id="inv1", target=hope_id,
            extra={"card_id": "hope_lv0"},
        ))

        played = [game.state.get_card_instance(iid).card_id
                  for iid in inv.play_area]
        assert "zeal_lv0" not in played
        assert "augur_lv0" not in played
        assert "zeal_lv0" in inv.discard
        assert "augur_lv0" in inv.discard

    def test_exhaust_evade_with_base_agility_5(self, game):
        """横置霍普：以基础敏捷5躲避（敏捷3对躲避4本不够）。"""
        hope_id = _equip_hope(game)
        enemy = _spawn_enemy(game)
        inv = game.state.get_investigator("inv1")
        impl = game.card_registry.active_instances[hope_id]
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]

        assert impl.activate_evade(game.state, "inv1") is True

        assert game.state.get_card_instance(hope_id).exhausted is True
        assert enemy.exhausted is True
        assert "enemy_1" not in inv.threat_area  # 脱离交战
        loc = game.state.get_location("test_location")
        assert "enemy_1" in loc.enemies

    def test_discard_evade_auto_success_and_recycle(self, game):
        """弃置霍普：自动躲避，洗回牌库，唤回弃牌堆中的 Zeal。"""
        hope_id = _equip_hope(game)
        enemy = _spawn_enemy(game)
        inv = game.state.get_investigator("inv1")
        inv.discard = ["zeal_lv0"]
        impl = game.card_registry.active_instances[hope_id]

        assert impl.activate_evade_discard(game.state, "inv1") is True

        assert enemy.exhausted is True
        assert "enemy_1" not in inv.threat_area
        assert hope_id not in inv.play_area
        assert "hope_lv0" in inv.deck  # 洗回牌库
        # Zeal 从弃牌堆入场
        played = [game.state.get_card_instance(iid).card_id
                  for iid in inv.play_area]
        assert "zeal_lv0" in played
        assert "zeal_lv0" not in inv.discard
