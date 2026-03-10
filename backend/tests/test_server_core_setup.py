"""Tests for the core campaign playable server setup helpers."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def test_parse_deck_text_formats():
    from frontend.server_core import _parse_deck_text

    deck = _parse_deck_text(
        """
        # comment
        2 machete_lv0
        guts_lv0 x2
        perception_lv0 *2
        emergency_cache_lv0
        """.strip()
    )
    assert deck.count("machete_lv0") == 2
    assert deck.count("guts_lv0") == 2
    assert deck.count("perception_lv0") == 2
    assert deck.count("emergency_cache_lv0") == 1


def test_create_game_accepts_investigator_and_deck_text():
    from frontend.server_core import create_game

    g = create_game(
        scenario_id="the_gathering",
        investigator_id="roland_banks",
        deck_text="2 machete_lv0\n2 emergency_cache_lv0\nunknown_card\n",
    )
    inv = g.state.get_investigator("player")
    assert inv is not None
    assert inv.card_data.name_cn == "罗兰·班克斯"
    assert inv.health == 9
    assert inv.sanity == 5
    assert len(inv.deck) + len(inv.hand) >= 25  # setup draws 5

