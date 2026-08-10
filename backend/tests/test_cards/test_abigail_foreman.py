"""Tests for Abigail Foreman (Level 4). (06324)

[快速]附着/交换典籍（不占手槽）；[反应]横置：再次结算所附典籍的[行动]能力。
"""

import pytest

from backend.cards.seeker.abigail_foreman_lv4 import AbigailForeman
from backend.cards.seeker.old_book_of_lore_lv0 import OldBookOfLore
from backend.engine.event_bus import EventBus
from backend.engine.slots import SlotManager
from backend.models.enums import SlotType
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, ScenarioState,
)
from backend.tests.conftest import make_asset_data, make_investigator_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()
    state.slot_managers = {"inv1": SlotManager()}

    inv_data = make_investigator_data()
    state.card_database[inv_data.id] = inv_data
    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1",
    )
    inv.deck = ["card_a", "card_b", "card_c", "card_d"]
    state.investigators["inv1"] = inv

    state.card_database["abigail_foreman_lv4"] = make_asset_data(
        id="abigail_foreman_lv4", name="Abigail Foreman",
        slots=[SlotType.ALLY], traits=["ally", "miskatonic"],
    )
    state.card_database["old_book_of_lore_lv0"] = make_asset_data(
        id="old_book_of_lore_lv0", name="Old Book of Lore",
        slots=[SlotType.HAND], traits=["item", "tome"],
    )
    # 非典籍支援（不能附着）
    state.card_database["machete_lv0"] = make_asset_data(
        id="machete_lv0", name="Machete", slots=[SlotType.HAND],
        traits=["item", "weapon"],
    )

    abigail = CardInstance(
        instance_id="inst_abigail", card_id="abigail_foreman_lv4",
        owner_id="inv1", controller_id="inv1", slot_used=[SlotType.ALLY],
    )
    book = CardInstance(
        instance_id="inst_book", card_id="old_book_of_lore_lv0",
        owner_id="inv1", controller_id="inv1", slot_used=[SlotType.HAND],
    )
    machete = CardInstance(
        instance_id="inst_machete", card_id="machete_lv0",
        owner_id="inv1", controller_id="inv1", slot_used=[SlotType.HAND],
    )
    for inst in (abigail, book, machete):
        state.cards_in_play[inst.instance_id] = inst
        inv.play_area.append(inst.instance_id)
    mgr = state.slot_managers["inv1"]
    mgr.occupy("inst_abigail", [SlotType.ALLY], ["ally"])
    mgr.occupy("inst_book", [SlotType.HAND], ["item", "tome"])
    mgr.occupy("inst_machete", [SlotType.HAND], ["item", "weapon"])

    impl = AbigailForeman("inst_abigail")
    impl.register(bus, "inst_abigail")
    return state, bus, inv, impl, mgr


class TestAttach:
    def test_attach_tome_frees_hand_slot(self, setup):
        """附着典籍后其手槽被释放（不占手槽）。"""
        state, bus, inv, impl, mgr = setup
        assert mgr.available(SlotType.HAND) == 0  # 书+砍刀占满2手槽
        assert impl.activate(state, "inv1", tome_instance_id="inst_book") is True
        assert impl.attached_tome == "inst_book"
        assert mgr.available(SlotType.HAND) == 1  # 书的手槽已释放
        assert state.get_card_instance("inst_book").attached_to == "inst_abigail"

    def test_attach_requires_tome_trait(self, setup):
        state, bus, inv, impl, mgr = setup
        assert impl.activate(state, "inv1", tome_instance_id="inst_machete") is False
        assert impl.attached_tome is None

    def test_switch_restores_old_tome_slot(self, setup):
        """交换：换下的典籍重新占用栏位。"""
        state, bus, inv, impl, mgr = setup
        # 第二张典籍入场
        state.card_database["cryptic_grimoire_lv0"] = make_asset_data(
            id="cryptic_grimoire_lv0", name="Cryptic Grimoire",
            slots=[SlotType.HAND], traits=["item", "tome"],
        )
        grimoire = CardInstance(
            instance_id="inst_grimoire", card_id="cryptic_grimoire_lv0",
            owner_id="inv1", controller_id="inv1", slot_used=[SlotType.HAND],
        )
        state.cards_in_play["inst_grimoire"] = grimoire
        inv.play_area.append("inst_grimoire")
        mgr.occupy("inst_grimoire", [SlotType.HAND], ["item", "tome"])

        assert impl.activate(state, "inv1", tome_instance_id="inst_book") is True
        assert mgr.available(SlotType.HAND) == 0  # 砍刀+魔典占满
        assert impl.activate(state, "inv1",
                             tome_instance_id="inst_grimoire") is True
        assert impl.attached_tome == "inst_grimoire"
        # 书重新占槽，魔典释放：手槽仍占满（砍刀+书），释放的是魔典
        assert mgr.available(SlotType.HAND) == 0
        assert "inst_book" in mgr.get_cards_in_slot(SlotType.HAND)
        assert "inst_grimoire" not in mgr.get_cards_in_slot(SlotType.HAND)


class TestRepeat:
    def test_repeat_resolves_tome_ability_again(self, setup):
        """横置 Abigail：再次结算所附典籍的[行动]能力（智慧古书抽牌）。"""
        state, bus, inv, impl, mgr = setup
        impl.activate(state, "inv1", tome_instance_id="inst_book")
        book = state.get_card_instance("inst_book")

        assert impl.repeat(state, "inv1") is True
        abigail = state.get_card_instance("inst_abigail")
        assert abigail.exhausted is True
        # 古书的效果再次结算：查看顶3抽第1张，且古书自身被横置
        assert book.exhausted is True
        assert "card_a" in inv.hand
        assert len(inv.deck) == 3

    def test_repeat_requires_attachment_and_ready(self, setup):
        state, bus, inv, impl, mgr = setup
        assert impl.repeat(state, "inv1") is False  # 未附着
        impl.activate(state, "inv1", tome_instance_id="inst_book")
        state.get_card_instance("inst_abigail").exhausted = True
        assert impl.repeat(state, "inv1") is False  # 已横置
