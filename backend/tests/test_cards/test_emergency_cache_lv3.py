"""Tests for Emergency Cache (Level 3) — Neutral event."""

from backend.cards.neutral.emergency_cache_lv3 import EmergencyCacheLv3
from backend.engine.event_bus import EventContext
from backend.models.enums import GameEvent
from backend.models.state import CardInstance
from backend.tests.conftest import make_asset_data


class TestEmergencyCacheLv3:
    def test_play_gains_4_resources(self, game):
        EmergencyCacheLv3("e1").register(game.event_bus, "e1")
        inv = game.state.get_investigator("test_investigator")
        inv.resources = 2
        ctx = EventContext(
            game_state=game.state, event=GameEvent.CARD_PLAYED,
            investigator_id="test_investigator",
            extra={"card_id": "emergency_cache_lv3"},
        )
        game.event_bus.emit(ctx)
        assert inv.resources == 6

    def test_resolve_supplies_combination(self, game):
        """组合分支：2资源 + 2补给到同地点支援卡。"""
        inv = game.state.get_investigator("test_investigator")
        inv.resources = 0
        game.register_card_data(make_asset_data(id="flash", uses={"supply": 1}))
        inst = CardInstance(
            instance_id="fl1", card_id="flash",
            owner_id="test_investigator", controller_id="test_investigator",
            uses={"supply": 1},
        )
        game.state.cards_in_play["fl1"] = inst
        inv.play_area.append("fl1")

        impl = EmergencyCacheLv3("e2")
        ok = impl.resolve_supplies(
            game.state, "test_investigator", resources=2, supplies={"fl1": 2},
        )
        assert ok is True
        assert inv.resources == 2
        assert game.state.get_card_instance("fl1").uses["supply"] == 3

    def test_resolve_supplies_rejects_wrong_total(self, game):
        impl = EmergencyCacheLv3("e3")
        assert impl.resolve_supplies(
            game.state, "test_investigator", resources=3, supplies={},
        ) is False

    def test_resolve_supplies_rejects_remote_controller(self, game):
        """补给只能给同地点调查员控制的支援。"""
        from backend.tests.conftest import make_investigator_data, make_location_data
        other_data = make_investigator_data(id="other_inv")
        game.register_card_data(other_data)
        loc2 = make_location_data(id="loc2")
        game.register_card_data(loc2)
        game.add_location("loc2", loc2)
        game.add_investigator("other_inv", other_data, starting_location="loc2")

        game.register_card_data(make_asset_data(id="flash"))
        inst = CardInstance(
            instance_id="fl2", card_id="flash",
            owner_id="other_inv", controller_id="other_inv",
        )
        game.state.cards_in_play["fl2"] = inst

        impl = EmergencyCacheLv3("e4")
        assert impl.resolve_supplies(
            game.state, "test_investigator", resources=0, supplies={"fl2": 4},
        ) is False
