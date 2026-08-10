"""Tests for Scroll of Secrets (Level 0 / Level 3).

官方 lv0：[行动]消耗+1秘密：查看任一牌堆或遭遇牌堆底牌，然后丢弃/
加入所有者手牌/放到牌堆顶/牌堆底。
官方 lv3：查看底3张；可弃1张、可入手1张；其余放顶或底任意顺序。
"""

import pytest

from backend.cards.seeker.scroll_of_secrets_lv0 import ScrollOfSecrets
from backend.cards.seeker.scroll_of_secrets_lv3 import ScrollOfSecretsLv3
from backend.engine.game import Game
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_asset_data, make_investigator_data, make_location_data,
)


def _setup(card_id, impl_cls):
    g = Game(f"test_{card_id}")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data()
    g.register_card_data(inv_data)
    loc_data = make_location_data(id="loc_a")
    g.register_card_data(loc_data)
    g.add_investigator(
        "player", inv_data,
        deck=["card_a", "card_b", "card_c", "card_d"],
        starting_location="loc_a",
    )
    g.add_location("loc_a", loc_data, clues=0)

    g.register_card_data(make_asset_data(
        id=card_id, name="Scroll of Secrets", cost=1,
        traits=["item", "tome"], uses={"secretss": 3}))
    inst = CardInstance(
        instance_id="inst_scroll", card_id=card_id,
        owner_id="player", controller_id="player",
    )
    inst.uses = {"secretss": 3}
    g.state.cards_in_play["inst_scroll"] = inst
    g.state.get_investigator("player").play_area.append("inst_scroll")

    impl = impl_cls("inst_scroll")
    impl.register(g.event_bus, "inst_scroll")
    return g, impl


class TestScrollOfSecretsLv0:
    def test_bottom_to_hand(self):
        """查看底牌(card_d)并加入手牌：消耗+扣秘密。"""
        g, impl = _setup("scroll_of_secrets_lv0", ScrollOfSecrets)
        inv = g.state.get_investigator("player")
        inst = g.state.get_card_instance("inst_scroll")
        assert impl.activate(g.state, "player", disposition="hand") is True
        assert "card_d" in inv.hand
        assert inv.deck == ["card_a", "card_b", "card_c"]
        assert inst.exhausted is True
        assert inst.uses["secretss"] == 2

    def test_bottom_to_top(self):
        """底牌放到牌堆顶。"""
        g, impl = _setup("scroll_of_secrets_lv0", ScrollOfSecrets)
        inv = g.state.get_investigator("player")
        assert impl.activate(g.state, "player", disposition="top") is True
        assert inv.deck == ["card_d", "card_a", "card_b", "card_c"]

    def test_bottom_discarded(self):
        """底牌丢弃。"""
        g, impl = _setup("scroll_of_secrets_lv0", ScrollOfSecrets)
        inv = g.state.get_investigator("player")
        assert impl.activate(g.state, "player", disposition="discard") is True
        assert inv.discard == ["card_d"]
        assert inv.deck == ["card_a", "card_b", "card_c"]

    def test_encounter_deck_bottom_discarded(self):
        """遭遇牌堆底牌丢弃到遭遇弃牌堆。"""
        g, impl = _setup("scroll_of_secrets_lv0", ScrollOfSecrets)
        g.state.scenario.encounter_deck = ["enc_a", "enc_b"]
        assert impl.activate(
            g.state, "player", target_encounter_deck=True,
            disposition="discard") is True
        assert g.state.scenario.encounter_deck == ["enc_a"]
        assert g.state.scenario.encounter_discard == ["enc_b"]


class TestScrollOfSecretsLv3:
    def test_bottom3_discard_and_hand(self):
        """底3张(b,c,d)：弃c、入手d、b回底。"""
        g, impl = _setup("scroll_of_secrets_lv3", ScrollOfSecretsLv3)
        inv = g.state.get_investigator("player")
        # looked = [card_b, card_c, card_d]（下标0=card_b，最底部=card_d）
        assert impl.activate(
            g.state, "player", discard_index=1, hand_index=2,
            placement="bottom") is True
        assert "card_d" in inv.hand
        assert inv.discard == ["card_c"]
        assert inv.deck == ["card_a", "card_b"]

    def test_bottom3_rest_to_top(self):
        """底3张放顶部（保持顺序）。"""
        g, impl = _setup("scroll_of_secrets_lv3", ScrollOfSecretsLv3)
        inv = g.state.get_investigator("player")
        assert impl.activate(g.state, "player", placement="top") is True
        assert inv.deck == ["card_b", "card_c", "card_d", "card_a"]

    def test_cannot_give_and_discard_same_card(self):
        g, impl = _setup("scroll_of_secrets_lv3", ScrollOfSecretsLv3)
        assert impl.activate(
            g.state, "player", discard_index=0, hand_index=0) is False
