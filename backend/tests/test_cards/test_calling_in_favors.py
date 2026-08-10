"""Tests for Calling in Favors (Level 0) — Neutral event."""

from backend.cards.neutral.calling_in_favors_lv0 import CallingInFavors
from backend.engine.event_bus import EventContext
from backend.models.enums import GameEvent
from backend.models.state import CardInstance
from backend.tests.conftest import make_asset_data


def _play(game):
    CallingInFavors("c1").register(game.event_bus, "c1")
    ctx = EventContext(
        game_state=game.state, event=GameEvent.CARD_PLAYED,
        investigator_id="test_investigator",
        extra={"card_id": "calling_in_favors_lv0"},
    )
    game.event_bus.emit(ctx)
    return ctx


def _add_ally(game, inv, card_id, cost, iid):
    game.register_card_data(make_asset_data(id=card_id, cost=cost, traits=["ally"]))
    inst = CardInstance(
        instance_id=iid, card_id=card_id,
        owner_id=inv.investigator_id, controller_id=inv.investigator_id,
    )
    game.state.cards_in_play[iid] = inst
    inv.play_area.append(iid)
    return inst


class TestCallingInFavors:
    def test_return_ally_and_play_discounted(self, game):
        """收回3费盟友 → 牌堆顶9张中打出5费盟友，只付2。"""
        inv = game.state.get_investigator("test_investigator")
        inv.resources = 5
        _add_ally(game, inv, "old_ally", 3, "ally_inst")
        game.register_card_data(make_asset_data(id="new_ally", cost=5, traits=["ally"]))
        inv.deck = ["filler1", "new_ally", "filler2", "filler3"]

        ctx = _play(game)

        assert "old_ally" in inv.hand
        assert "ally_inst" not in inv.play_area
        # 新盟友已打出，费用 5-3=2
        assert inv.resources == 3
        new_insts = [
            game.state.get_card_instance(i) for i in inv.play_area
        ]
        assert any(i is not None and i.card_id == "new_ally" for i in new_insts)
        assert "new_ally" not in inv.deck
        # 牌堆已混洗但张数不变
        assert len(inv.deck) == 3
        assert ctx.extra["calling_in_favors"]["played"] == "new_ally"

    def test_ally_beyond_top_9_not_found(self, game):
        inv = game.state.get_investigator("test_investigator")
        inv.resources = 5
        _add_ally(game, inv, "old_ally", 3, "ally_inst")
        game.register_card_data(make_asset_data(id="far_ally", cost=2, traits=["ally"]))
        inv.deck = [f"f{i}" for i in range(9)] + ["far_ally"]

        ctx = _play(game)
        assert "old_ally" in inv.hand
        assert "far_ally" in inv.deck
        assert inv.resources == 5

    def test_no_ally_in_play_no_effect(self, game):
        inv = game.state.get_investigator("test_investigator")
        inv.deck = ["x", "y"]
        ctx = _play(game)
        assert ctx.extra["calling_in_favors"] == "no_ally"
        assert len(inv.deck) == 2
