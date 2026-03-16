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

    # Build a 30-card deck (required now that roland_banks has deck_requirements)
    deck_lines = [
        "2 machete_lv0",
        "2 emergency_cache_lv0",
        "2 guard_dog_lv0",
        "2 beat_cop_lv0",
        "2 dodge_lv0",
        "2 evidence_lv0",
        "2 vicious_blow_lv0",
        "2 guts_lv0",
        "2 overpower_lv0",
        "2 manual_dexterity_lv0",
        "2 unexpected_courage_lv0",
        "2 perception_lv0",
        "2 knife_lv0",
        "2 flashlight_lv0",
        "2 working_a_hunch_lv0",
    ]
    g = create_game(
        scenario_id="the_gathering",
        investigator_id="roland_banks",
        deck_text="\n".join(deck_lines),
    )
    inv = g.state.get_investigator("player")
    assert inv is not None
    assert inv.card_data.name_cn == "罗兰·班克斯"
    assert inv.health == 9
    assert inv.sanity == 5
    assert len(inv.deck) + len(inv.hand) >= 25  # setup draws 5

