"""Integration tests: slot limits are enforced when playing assets."""

import pytest

from backend.models.enums import Action, CardType, GameEvent, PlayerClass, SlotType
from backend.models.state import CardData
from backend.tests.conftest import make_asset_data


def _register(game, *card_datas):
    for cd in card_datas:
        game.register_card_data(cd)


def _hand(game, *card_ids):
    inv = game.state.get_investigator("test_investigator")
    inv.hand.extend(card_ids)
    inv.resources = 20
    return inv


@pytest.fixture
def assets(game):
    """Two hand-slot weapons (non-tome) + one tome asset, all cost 1."""
    gun1 = make_asset_data(
        id="gun1", name="Gun 1", cost=1, slots=[SlotType.HAND], traits=["item", "weapon"]
    )
    gun2 = make_asset_data(
        id="gun2", name="Gun 2", cost=1, slots=[SlotType.HAND], traits=["item", "weapon"]
    )
    gun3 = make_asset_data(
        id="gun3", name="Gun 3", cost=1, slots=[SlotType.HAND], traits=["item", "weapon"]
    )
    tome = make_asset_data(
        id="tome1", name="Tome 1", cost=1, slots=[SlotType.HAND], traits=["item", "tome"]
    )
    _register(game, gun1, gun2, gun3, tome)
    return game


class TestSlotEnforcement:
    def test_play_fails_when_slots_full_and_nothing_changes(self, assets):
        inv = _hand(assets, "gun1", "gun2", "gun3")
        resolver = assets.action_resolver

        assert resolver.perform_action("test_investigator", Action.PLAY, card_id="gun1")
        assert resolver.perform_action("test_investigator", Action.PLAY, card_id="gun2")

        resources_before = inv.resources
        hand_before = list(inv.hand)
        ok = resolver.perform_action("test_investigator", Action.PLAY, card_id="gun3")

        assert not ok
        # Nothing was paid / moved
        assert inv.resources == resources_before
        assert inv.hand == hand_before
        # Conflict info for the UI
        conflict = resolver.last_slot_conflict
        assert conflict is not None
        assert conflict["needed"] == {"hand": 1}
        candidate_ids = {c["instance_id"] for c in conflict["candidates"]}
        assert len(candidate_ids) == 2  # gun1 and gun2 are in play

    def test_play_succeeds_after_slot_discards(self, assets):
        inv = _hand(assets, "gun1", "gun2", "gun3")
        resolver = assets.action_resolver

        resolver.perform_action("test_investigator", Action.PLAY, card_id="gun1")
        resolver.perform_action("test_investigator", Action.PLAY, card_id="gun2")

        mgr = assets.state.slot_managers["test_investigator"]
        assert mgr.count_used(SlotType.HAND) == 2

        gun1_iid = next(
            iid for iid in inv.play_area
            if assets.state.get_card_instance(iid).card_id == "gun1"
        )
        ok = resolver.perform_action(
            "test_investigator", Action.PLAY,
            card_id="gun3", slot_discards=[gun1_iid],
        )
        assert ok
        # gun1 discarded, gun3 in play; hand slots still 2 used
        assert "gun1" in inv.discard
        assert gun1_iid not in inv.play_area
        assert mgr.count_used(SlotType.HAND) == 2
        played = {assets.state.get_card_instance(iid).card_id for iid in inv.play_area}
        assert played == {"gun2", "gun3"}

    def test_insufficient_slot_discards_does_not_discard(self, assets):
        """If discards can't satisfy the deficit, nothing is discarded."""
        inv = _hand(assets, "gun1", "gun2", "gun3")
        resolver = assets.action_resolver
        resolver.perform_action("test_investigator", Action.PLAY, card_id="gun1")
        resolver.perform_action("test_investigator", Action.PLAY, card_id="gun2")

        # Discard list valid length (1 needed) but pass a bogus id → reject
        ok = resolver.perform_action(
            "test_investigator", Action.PLAY,
            card_id="gun3", slot_discards=["nonexistent_instance"],
        )
        assert not ok
        assert inv.discard == []

    def test_slot_conflict_cleared_on_success(self, assets):
        inv = _hand(assets, "gun1")
        resolver = assets.action_resolver
        assert resolver.perform_action("test_investigator", Action.PLAY, card_id="gun1")
        assert resolver.last_slot_conflict is None


class TestToteBagIntegration:
    def test_tome_only_restricted_slots(self, assets):
        """With tote's restricted bonus, tomes exceed base hand limit; non-tomes don't."""
        mgr = assets.state.slot_managers["test_investigator"]
        mgr.add_restricted_bonus(SlotType.HAND, 2, trait="tome", source="tote")

        inv = _hand(assets, "gun1", "gun2", "gun3", "tome1")
        resolver = assets.action_resolver

        assert resolver.perform_action("test_investigator", Action.PLAY, card_id="gun1")
        assert resolver.perform_action("test_investigator", Action.PLAY, card_id="gun2")
        # Third non-tome weapon: rejected despite restricted bonus
        assert not resolver.perform_action(
            "test_investigator", Action.PLAY, card_id="gun3"
        )
        # But a tome fits
        assert resolver.perform_action(
            "test_investigator", Action.PLAY, card_id="tome1"
        )

    def test_destroyed_asset_frees_slot(self, assets):
        """DamageEngine removal must vacate slots (regression: slot leak)."""
        inv = _hand(assets, "gun1", "gun2", "gun3")
        resolver = assets.action_resolver
        resolver.perform_action("test_investigator", Action.PLAY, card_id="gun1")
        resolver.perform_action("test_investigator", Action.PLAY, card_id="gun2")

        gun1_iid = next(
            iid for iid in inv.play_area
            if assets.state.get_card_instance(iid).card_id == "gun1"
        )
        assets.damage_engine._remove_card_from_play(gun1_iid)

        mgr = assets.state.slot_managers["test_investigator"]
        assert mgr.count_used(SlotType.HAND) == 1
        # Now the third gun can be played
        assert resolver.perform_action("test_investigator", Action.PLAY, card_id="gun3")

    def test_discard_emits_card_leaves_play(self, assets):
        """Discarding for slots emits CARD_LEAVES_PLAY (e.g. Tote reclaim)."""
        inv = _hand(assets, "gun1", "gun2", "gun3")
        resolver = assets.action_resolver
        resolver.perform_action("test_investigator", Action.PLAY, card_id="gun1")
        resolver.perform_action("test_investigator", Action.PLAY, card_id="gun2")

        seen = []
        from backend.models.enums import TimingPriority

        def listener(ctx):
            seen.append(ctx.target)

        assets.event_bus.register(
            GameEvent.CARD_LEAVES_PLAY, listener, priority=TimingPriority.AFTER
        )

        gun1_iid = next(
            iid for iid in inv.play_area
            if assets.state.get_card_instance(iid).card_id == "gun1"
        )
        resolver.perform_action(
            "test_investigator", Action.PLAY,
            card_id="gun3", slot_discards=[gun1_iid],
        )
        assert gun1_iid in seen
