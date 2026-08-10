"""Tests for Crisis of Identity (Level 0) — Lola Hayes signature weakness."""

from backend.cards.neutral.crisis_of_identity_lv0 import CrisisOfIdentity
from backend.engine.event_bus import EventContext
from backend.models.enums import CardType, GameEvent, PlayerClass
from backend.models.state import CardData, CardInstance
from backend.tests.conftest import make_asset_data


def _reveal(game, role="guardian", deck_top=None):
    CrisisOfIdentity("c1").register(game.event_bus, "c1")
    inv = game.state.get_investigator("test_investigator")
    inv.hand.append("crisis_of_identity_lv0")
    game.state.scenario.vars["role_test_investigator"] = role
    if deck_top is not None:
        inv.deck = [deck_top, "filler"]
    ctx = EventContext(
        game_state=game.state, event=GameEvent.CARD_DRAWN,
        investigator_id="test_investigator",
        extra={"card_id": "crisis_of_identity_lv0"},
    )
    game.event_bus.emit(ctx)
    return ctx, inv


def _add_asset(game, inv, card_id, card_class, iid):
    game.register_card_data(make_asset_data(id=card_id, card_class=card_class))
    inst = CardInstance(
        instance_id=iid, card_id=card_id,
        owner_id=inv.investigator_id, controller_id=inv.investigator_id,
    )
    game.state.cards_in_play[iid] = inst
    inv.play_area.append(iid)


class TestCrisisOfIdentity:
    def test_discards_role_cards_and_switches_role(self, game):
        """丢弃所有守卫者在场卡；牌堆顶是流浪者卡 → 角色切换为流浪者。"""
        inv = game.state.get_investigator("test_investigator")
        _add_asset(game, inv, "guardian_asset", PlayerClass.GUARDIAN, "g1")
        _add_asset(game, inv, "seeker_asset", PlayerClass.SEEKER, "s1")
        game.register_card_data(make_asset_data(
            id="rogue_card", card_class=PlayerClass.ROGUE))

        ctx, inv = _reveal(game, role="guardian", deck_top="rogue_card")

        assert "guardian_asset" in inv.discard
        assert "g1" not in inv.play_area
        assert "s1" in inv.play_area  # 非当前角色不受影响
        assert "rogue_card" in inv.discard
        assert game.state.scenario.vars["role_test_investigator"] == "rogue"
        assert "crisis_of_identity_lv0" in inv.discard
        assert ctx.extra["crisis_of_identity"]["new_role"] == "rogue"

    def test_weakness_top_card_switches_to_neutral(self, game):
        game.register_card_data(CardData(
            id="weak_card", name="W", name_cn="W", type=CardType.TREACHERY,
            card_class=PlayerClass.GUARDIAN, subtype="weakness",
        ))
        ctx, inv = _reveal(game, role="guardian", deck_top="weak_card")
        assert game.state.scenario.vars["role_test_investigator"] == "neutral"

    def test_empty_deck_keeps_role(self, game):
        CrisisOfIdentity("c1").register(game.event_bus, "c1")
        inv = game.state.get_investigator("test_investigator")
        inv.hand.append("crisis_of_identity_lv0")
        game.state.scenario.vars["role_test_investigator"] = "mystic"
        inv.deck = []
        ctx = EventContext(
            game_state=game.state, event=GameEvent.CARD_DRAWN,
            investigator_id="test_investigator",
            extra={"card_id": "crisis_of_identity_lv0"},
        )
        game.event_bus.emit(ctx)
        assert game.state.scenario.vars["role_test_investigator"] == "mystic"
