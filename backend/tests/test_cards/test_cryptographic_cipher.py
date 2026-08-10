"""Tests for Cryptographic Cipher (Level 0). (07021)

[快速]横置+1秘密：调查+1隐蔽；[行动]横置+1秘密：调查-2隐蔽。
"""

import pytest

from backend.cards.seeker.cryptographic_cipher_lv0 import CryptographicCipher
from backend.engine.game import Game
from backend.models.enums import Action, ChaosTokenType
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_asset_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def game():
    g = Game("test_cipher")
    g.chaos_bag.seed(42)
    inv_data = make_investigator_data(intellect=3)
    g.register_card_data(inv_data)
    loc_data = make_location_data(id="loc_a", shroud=2)
    g.register_card_data(loc_data)
    g.add_investigator("inv1", inv_data, starting_location="loc_a")
    g.add_location("loc_a", loc_data, clues=3)
    g.register_card_data(make_asset_data(
        id="cryptographic_cipher_lv0", traits=["item", "tool"],
        uses={"secretss": 3}))
    inst = CardInstance(
        instance_id="inst_cipher", card_id="cryptographic_cipher_lv0",
        owner_id="inv1", controller_id="inv1",
    )
    inst.uses = {"secretss": 3}  # 数据双 s 键兼容
    g.state.cards_in_play["inst_cipher"] = inst
    g.state.get_investigator("inv1").play_area.append("inst_cipher")
    impl = CryptographicCipher("inst_cipher")
    impl.register(g.event_bus, "inst_cipher")
    return g, inst, impl


class TestCryptographicCipher:
    def test_deep_investigation_lowers_shroud(self, game):
        """[行动]：-2隐蔽（2→0 自动成功），花1秘密并横置。"""
        g, inst, impl = game
        g.chaos_bag.tokens = [ChaosTokenType.MINUS_1]
        assert impl.activate(g.state, "inv1") is True
        assert inst.uses["secretss"] == 2
        assert inst.exhausted is True
        assert g.action_resolver.perform_action("inv1", Action.INVESTIGATE)
        inv = g.state.get_investigator("inv1")
        assert inv.clues == 1  # 难度0：自动成功

    def test_quick_investigation_raises_shroud(self, game):
        """[快速]：+1隐蔽（2→3，3-1=2<3 失败）。"""
        g, inst, impl = game
        g.chaos_bag.tokens = [ChaosTokenType.MINUS_1]
        assert impl.activate_quick(g.state, "inv1") is True
        assert g.action_resolver.perform_action("inv1", Action.INVESTIGATE)
        inv = g.state.get_investigator("inv1")
        assert inv.clues == 0

    def test_requires_secrets(self, game):
        g, inst, impl = game
        inst.uses["secretss"] = 0
        assert impl.activate(g.state, "inv1") is False
        assert impl.activate_quick(g.state, "inv1") is False
