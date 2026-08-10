"""Regression tests: chaos-bag-dependent cards must work via the production
activation path (Game wiring), not only when tests call bind_chaos_bag by hand.

Covers the 2026-08 audit finding that Final Rhapsody / Rex's Curse were
inert in real games because nothing in production injected the chaos bag.
"""

from backend.engine.game import Game
from backend.models.enums import ChaosTokenType
from backend.tests.conftest import (
    make_event_data,
    make_investigator_data,
    make_location_data,
)


def _make_game(deck):
    g = Game("test")
    inv_data = make_investigator_data()
    g.register_card_data(inv_data)
    loc_data = make_location_data(clue_value=0, connections=[])
    g.register_card_data(loc_data)
    g.add_investigator("player", inv_data, starting_location="test_location")
    g.add_location("test_location", loc_data, clues=0)
    g.card_registry.discover_cards()
    inv = g.state.get_investigator("player")
    inv.deck = list(deck)
    return g, inv


class TestChaosBagInjection:
    def test_final_rhapsody_draws_from_real_bag(self):
        g, inv = _make_game(["final_rhapsody_lv0"])
        g.register_card_data(make_event_data(id="final_rhapsody_lv0"))
        # 抽取为非破坏性（有放回）：全骷髅袋保证确定性——5抽必中5
        g.chaos_bag.tokens = [ChaosTokenType.SKULL] * 3
        inv.damage = 0
        inv.horror = 0
        g.action_resolver._draw("player")
        assert inv.damage == 5
        assert inv.horror == 5
        assert "final_rhapsody_lv0" in inv.discard

    def test_rexs_curse_gets_bag_on_draw(self):
        g, inv = _make_game(["rexs_curse_lv0"])
        g.register_card_data(make_event_data(id="rexs_curse_lv0"))
        g.action_resolver._draw("player")
        # 雷克斯的诅咒为持续威胁区卡：注册应保持且已注入混沌袋
        impl = next(
            (impl for impl in g.card_registry._active_cards.values()
             if impl.card_id == "rexs_curse_lv0"),
            None,
        )
        assert impl is not None, "诅咒实现应保持注册（威胁区持续卡）"
        assert impl._chaos_bag is g.chaos_bag
