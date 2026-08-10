"""Tests for Rod of Animalism (Level 1)."""

from backend.cards.neutral.rod_of_animalism_lv1 import RodOfAnimalism
from backend.engine.event_bus import EventContext
from backend.models.enums import CardType, GameEvent, PlayerClass, SlotType
from backend.models.state import CardData, CardInstance


def _equip(game):
    inv = game.state.get_investigator("test_investigator")
    ci = CardInstance(
        instance_id="rod_1", card_id="rod_of_animalism_lv1",
        owner_id="test_investigator", controller_id="test_investigator",
    )
    game.state.cards_in_play["rod_1"] = ci
    inv.play_area.append("rod_1")
    impl = RodOfAnimalism("rod_1")
    impl.register(game.event_bus, "rod_1")
    ctx = EventContext(
        game_state=game.state, event=GameEvent.CARD_ENTERS_PLAY,
        investigator_id="test_investigator", target="rod_1",
        extra={"card_id": "rod_of_animalism_lv1"},
    )
    game.event_bus.emit(ctx)
    return impl


def _emit_enters(game, card_id, instance_id):
    ctx = EventContext(
        game_state=game.state, event=GameEvent.CARD_ENTERS_PLAY,
        investigator_id="test_investigator", target=instance_id,
        extra={"card_id": card_id},
    )
    game.event_bus.emit(ctx)
    return ctx


class TestRodOfAnimalism:
    def test_grants_creature_only_ally_slots(self, game):
        """进场：2个仅限生物的额外盟友槽。"""
        _equip(game)
        mgr = game.state.slot_managers["test_investigator"]
        # 基础盟友槽1 + 生物限定2
        assert mgr.effective_limit(SlotType.ALLY, ["creature"]) == 3
        # 非生物卡只能用基础槽
        assert mgr.effective_limit(SlotType.ALLY, ["item"]) == 1

    def test_slots_removed_on_leave(self, game):
        """离场：移除额外槽位。"""
        _equip(game)
        ctx = EventContext(
            game_state=game.state, event=GameEvent.CARD_LEAVES_PLAY,
            investigator_id="test_investigator", target="rod_1",
            extra={"card_id": "rod_of_animalism_lv1"},
        )
        game.event_bus.emit(ctx)
        mgr = game.state.slot_managers["test_investigator"]
        assert mgr.effective_limit(SlotType.ALLY, ["creature"]) == 1

    def test_creature_play_refunds_one(self, game):
        """打出生物支援卡：返还1资源。"""
        _equip(game)
        creature = CardData(
            id="hound", name="Hound", name_cn="猎犬",
            type=CardType.ASSET, card_class=PlayerClass.NEUTRAL,
            cost=2, traits=["creature"], slots=[SlotType.ALLY],
        )
        game.register_card_data(creature)
        inv = game.state.get_investigator("test_investigator")
        before = inv.resources
        ctx = _emit_enters(game, "hound", "hound_1")
        assert inv.resources == before + 1
        assert ctx.extra["rod_of_animalism_refund"] == 1

    def test_non_creature_no_refund(self, game):
        """非生物支援卡不返还。"""
        _equip(game)
        item = CardData(
            id="lantern", name="Lantern", name_cn="提灯",
            type=CardType.ASSET, card_class=PlayerClass.NEUTRAL,
            cost=2, traits=["item"],
        )
        game.register_card_data(item)
        inv = game.state.get_investigator("test_investigator")
        before = inv.resources
        ctx = _emit_enters(game, "lantern", "lantern_1")
        assert inv.resources == before
        assert "rod_of_animalism_refund" not in ctx.extra
