"""Tests for Spirit-Speaker (Level 0) — Akachi Onyele signature asset."""

from backend.cards.neutral.spirit_speaker_lv0 import SpiritSpeaker
from backend.models.state import CardInstance
from backend.tests.conftest import make_asset_data


def _setup(game, charges=3):
    game.register_card_data(make_asset_data(id="spirit_speaker_lv0", cost=2))
    game.register_card_data(make_asset_data(
        id="shrivelling", traits=["spell"], uses={"charges": charges}))
    inv = game.state.get_investigator("test_investigator")
    for iid, cid in (("sp1", "spirit_speaker_lv0"), ("sh1", "shrivelling")):
        inst = CardInstance(
            instance_id=iid, card_id=cid,
            owner_id="test_investigator", controller_id="test_investigator",
            uses={"charges": charges} if cid == "shrivelling" else {},
        )
        game.state.cards_in_play[iid] = inst
        inv.play_area.append(iid)
    impl = SpiritSpeaker("sp1")
    impl.register(game.event_bus, "sp1")
    return impl, inv


class TestSpiritSpeaker:
    def test_list_targets(self, game):
        impl, inv = _setup(game)
        assert impl.list_targets(game.state, "test_investigator") == ["sh1"]

    def test_cash_out_charges(self, game):
        """兑现：3充能 → +3资源，支援入弃牌堆，灵言者消耗。"""
        impl, inv = _setup(game, charges=3)
        inv.resources = 1
        ok = impl.activate_resolve(
            game.state, "test_investigator", target_instance_id="sh1", mode="cash",
        )
        assert ok is True
        assert inv.resources == 4
        assert "shrivelling" in inv.discard
        assert "sh1" not in inv.play_area
        assert game.state.get_card_instance("sp1").exhausted

    def test_return_to_hand(self, game):
        impl, inv = _setup(game)
        ok = impl.activate_resolve(
            game.state, "test_investigator", target_instance_id="sh1", mode="return",
        )
        assert ok is True
        assert "shrivelling" in inv.hand
        assert "sh1" not in game.state.cards_in_play

    def test_auto_pick_first_target(self, game):
        impl, inv = _setup(game)
        assert impl.activate_resolve(game.state, "test_investigator") is True
        assert "shrivelling" in inv.hand

    def test_exhausted_cannot_activate(self, game):
        impl, inv = _setup(game)
        game.state.get_card_instance("sp1").exhausted = True
        assert impl.activate_resolve(game.state, "test_investigator") is False

    def test_rejects_invalid_target(self, game):
        impl, inv = _setup(game)
        assert impl.activate_resolve(
            game.state, "test_investigator", target_instance_id="sp1",
        ) is False
