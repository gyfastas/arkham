"""Tests for Angered Spirits (Level 0) — Akachi Onyele signature weakness."""

from backend.cards.neutral.angered_spirits_lv0 import AngeredSpirits
from backend.engine.event_bus import EventContext
from backend.models.enums import GameEvent, PlayerClass
from backend.models.state import CardInstance
from backend.tests.conftest import make_asset_data, make_investigator_card


def _reveal(game):
    impl = AngeredSpirits("a1")
    impl.register(game.event_bus, "a1")
    inv = game.state.get_investigator("test_investigator")
    inv.hand.append("angered_spirits_lv0")
    ctx = EventContext(
        game_state=game.state, event=GameEvent.CARD_DRAWN,
        investigator_id="test_investigator",
        extra={"card_id": "angered_spirits_lv0"},
    )
    game.event_bus.emit(ctx)
    return impl, inv, game.state.get_card_instance(inv.threat_area[0])


def _add_spell(game, inv, charges=2, exhausted=False, iid="spell_1"):
    game.register_card_data(make_asset_data(
        id="test_spell", traits=["spell"], uses={"charges": charges},
    ))
    inst = CardInstance(
        instance_id=iid, card_id="test_spell",
        owner_id=inv.investigator_id, controller_id=inv.investigator_id,
        uses={"charges": charges}, exhausted=exhausted,
    )
    game.state.cards_in_play[iid] = inst
    inv.play_area.append(iid)
    return inst


class TestAngeredSpirits:
    def test_revelation_enters_threat_area(self, game):
        impl, inv, spirits = _reveal(game)
        assert "angered_spirits_lv0" not in inv.hand
        assert spirits.card_id == "angered_spirits_lv0"

    def test_move_charge_from_spell(self, game):
        impl, inv, spirits = _reveal(game)
        spell = _add_spell(game, inv, charges=2)

        assert impl.activate_move_charge(game.state, "test_investigator") is True
        assert spell.exhausted
        assert spell.uses["charges"] == 1
        assert spirits.uses["charges"] == 1

    def test_move_charge_skips_invalid_targets(self, game):
        """已消耗/无充能/非法术的支援不可选。"""
        impl, inv, spirits = _reveal(game)
        _add_spell(game, inv, charges=0, iid="empty_spell")  # 无充能
        assert impl.activate_move_charge(game.state, "test_investigator") is False

    def test_game_end_penalty_with_few_charges(self, game):
        """终局充能<4：1点肉体创伤。"""
        impl, inv, spirits = _reveal(game)
        inv.investigator_card = make_investigator_card()
        spirits.uses["charges"] = 2

        assert impl.game_end_penalty(game.state, "test_investigator") is True
        assert inv.investigator_card.physical_trauma == 1
        trauma = game.state.scenario.vars["trauma"]["test_investigator"]
        assert trauma["physical"] == 1

    def test_game_end_no_penalty_with_four_charges(self, game):
        impl, inv, spirits = _reveal(game)
        inv.investigator_card = make_investigator_card()
        spirits.uses["charges"] = 4
        assert impl.game_end_penalty(game.state, "test_investigator") is False
        assert inv.investigator_card.physical_trauma == 0
