"""Tests for Dayana Esperence (Level 3). (05279)

[fast]叠加手牌中非弱点法术事件（限1张）；消耗+1秘密打出叠加事件，
打出后事件不弃置而维持叠加（经完整 PLAY 行动验证）。
"""

import pytest
from backend.cards.mystic.dayana_esperence_lv3 import DayanaEsperence
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import Action, CardType, GameEvent, PlayerClass, SlotType
from backend.models.state import CardData, CardInstance
from backend.tests.conftest import (
    make_asset_data, make_event_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)
    inv_data = make_investigator_data()
    g.register_card_data(inv_data)
    loc = make_location_data()
    g.register_card_data(loc)

    dayana = CardData(
        id="dayana_esperence_lv3", name="Dayana Esperence", name_cn="黛雅娜",
        type=CardType.ASSET, card_class=PlayerClass.MYSTIC, cost=4,
        slots=[SlotType.ALLY], traits=["ally", "witch"], unique=True,
        uses={"secrets": 3}, health=3, sanity=1,
    )
    g.register_card_data(dayana)
    g.register_card_data(make_event_data(
        id="test_spell_event", name="Test Spell", cost=0))
    g.state.card_database["test_spell_event"].traits = ["spell"]

    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)
    g.card_registry.register_class(DayanaEsperence)
    return g


def _equip_dayana(game):
    inv = game.state.get_investigator("inv1")
    inst = CardInstance(
        instance_id="inst_dayana", card_id="dayana_esperence_lv3",
        owner_id="inv1", controller_id="inv1",
        slot_used=[SlotType.ALLY],
    )
    inst.uses = {"secrets": 3}
    game.state.cards_in_play["inst_dayana"] = inst
    inv.play_area.append("inst_dayana")
    impl = game.card_registry.activate_card(
        "dayana_esperence_lv3", "inst_dayana", game.event_bus)
    return inst, impl


class TestDayanaEsperence:
    def test_attach_spell_event_from_hand(self, game):
        """叠加手牌中的法术事件（限1张）。"""
        inv = game.state.get_investigator("inv1")
        inv.hand = ["test_spell_event"]
        inst, impl = _equip_dayana(game)
        assert impl.attach_event(game.state, "inv1", "test_spell_event") is True
        assert inv.hand == []
        assert impl.attached_event == "test_spell_event"
        # 限1张
        inv.hand.append("test_spell_event")
        assert impl.attach_event(game.state, "inv1", "test_spell_event") is False

    def test_attach_rejects_non_spell(self, game):
        inv = game.state.get_investigator("inv1")
        game.state.card_database["tactic_event"] = make_event_data(
            id="tactic_event", name="Tactic", cost=0)
        game.state.card_database["tactic_event"].traits = ["tactic"]
        inv.hand = ["tactic_event"]
        _, impl = _equip_dayana(game)
        assert impl.attach_event(game.state, "inv1", "tactic_event") is False

    def test_play_attached_full_flow(self, game):
        """消耗+1秘密打出叠加事件；事件结算后重新叠加而非弃置。"""
        inv = game.state.get_investigator("inv1")
        inv.hand = ["test_spell_event"]
        inv.resources = 0
        inv.actions_remaining = 3
        inst, impl = _equip_dayana(game)
        impl.attach_event(game.state, "inv1", "test_spell_event")

        card_id = impl.play_attached(game.state, "inv1")
        assert card_id == "test_spell_event"
        assert inst.exhausted is True
        assert inst.uses["secrets"] == 2
        assert "test_spell_event" in inv.hand

        # 会话层按正常流程打出该事件
        ok = game.action_resolver.perform_action(
            "inv1", Action.PLAY, card_id="test_spell_event")
        assert ok is True
        # 结算后：不在弃牌堆，重新叠加到黛雅娜
        assert "test_spell_event" not in inv.discard
        assert impl.attached_event == "test_spell_event"

    def test_play_attached_requires_secret_and_ready(self, game):
        inv = game.state.get_investigator("inv1")
        inv.hand = ["test_spell_event"]
        inst, impl = _equip_dayana(game)
        impl.attach_event(game.state, "inv1", "test_spell_event")
        inst.uses["secrets"] = 0
        assert impl.play_attached(game.state, "inv1") is None
        inst.uses["secrets"] = 1
        inst.exhausted = True
        assert impl.play_attached(game.state, "inv1") is None
