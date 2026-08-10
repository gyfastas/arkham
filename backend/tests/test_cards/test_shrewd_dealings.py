"""Tests for Shrewd Dealings (Level 0)."""

from backend.cards.neutral.shrewd_dealings_lv0 import ShrewdDealings
from backend.engine.event_bus import EventContext
from backend.models.enums import CardType, GameEvent, PlayerClass
from backend.models.state import CardData, CardInstance
from backend.tests.conftest import make_investigator_data


def _equip(game):
    inv = game.state.get_investigator("test_investigator")
    ci = CardInstance(
        instance_id="sd_1", card_id="shrewd_dealings_lv0",
        owner_id="test_investigator", controller_id="test_investigator",
    )
    game.state.cards_in_play["sd_1"] = ci
    inv.play_area.append("sd_1")
    impl = ShrewdDealings("sd_1")
    impl.register(game.event_bus, "sd_1")
    return impl


def _play_item(game, item_id="flashlight_lv0", instance_id="item_1", cost=2, traits=("item",)):
    game.register_card_data(CardData(
        id=item_id, name=item_id, name_cn=item_id,
        type=CardType.ASSET, card_class=PlayerClass.NEUTRAL,
        cost=cost, traits=list(traits),
    ))
    ci = CardInstance(
        instance_id=instance_id, card_id=item_id,
        owner_id="test_investigator", controller_id="test_investigator",
    )
    game.state.cards_in_play[instance_id] = ci
    inv = game.state.get_investigator("test_investigator")
    inv.play_area.append(instance_id)
    ctx = EventContext(
        game_state=game.state, event=GameEvent.CARD_ENTERS_PLAY,
        investigator_id="test_investigator", target=instance_id,
        extra={"card_id": item_id},
    )
    game.event_bus.emit(ctx)
    return ctx, ci


class TestShrewdDealings:
    def test_item_cost_refund(self, game):
        """打出物品支援卡：返还1资源。"""
        _equip(game)
        inv = game.state.get_investigator("test_investigator")
        before = inv.resources
        ctx, _ = _play_item(game, cost=3)
        assert inv.resources == before + 1
        assert ctx.extra["shrewd_dealings_refund"] == 1

    def test_non_item_no_refund(self, game):
        """非物品卡不返还。"""
        _equip(game)
        inv = game.state.get_investigator("test_investigator")
        before = inv.resources
        ctx, _ = _play_item(game, item_id="beat_cop_lv0", instance_id="ally_1",
                            traits=("ally",))
        assert inv.resources == before
        assert "shrewd_dealings_refund" not in ctx.extra

    def test_transfer_to_investigator_at_location(self, game):
        """反应：将刚打出的物品转交同地点调查员控制。"""
        impl = _equip(game)
        other_data = make_investigator_data(id="inv2", name="Inv2")
        game.register_card_data(other_data)
        game.add_investigator("inv2", other_data, starting_location="test_location")
        _, ci = _play_item(game)

        assert impl.transfer_last_item(game.state, "inv2") is True
        inv1 = game.state.get_investigator("test_investigator")
        inv2 = game.state.get_investigator("inv2")
        assert ci.controller_id == "inv2"
        assert "item_1" not in inv1.play_area
        assert "item_1" in inv2.play_area

    def test_transfer_rejects_other_location(self, game):
        """目标在不同地点时不能转交。"""
        impl = _equip(game)
        other_data = make_investigator_data(id="inv2", name="Inv2")
        game.register_card_data(other_data)
        game.add_investigator("inv2", other_data, starting_location="elsewhere")
        _, ci = _play_item(game)

        assert impl.transfer_last_item(game.state, "inv2") is False
        assert ci.controller_id == "test_investigator"
