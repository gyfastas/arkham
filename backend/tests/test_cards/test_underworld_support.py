"""Tests for Underworld Support (Level 0) — deckbuilding rule helpers."""

from backend.cards.rogue.underworld_support_lv0 import UnderworldSupport
from backend.models.enums import CardType, PlayerClass
from backend.models.state import CardData


def _card(card_id, name, text="", subtype=""):
    return CardData(
        id=card_id,
        name=name,
        name_cn=name,
        type=CardType.EVENT,
        card_class=PlayerClass.ROGUE,
        text=text,
        subtype=subtype,
    )


class TestUnderworldSupport:
    def test_deck_size_adjustment(self):
        assert UnderworldSupport.deck_size_adjustment() == -5

    def test_duplicate_titles_flagged(self):
        db = {
            "a": _card("a", "Lucky!"),
            "b": _card("b", "Lucky!"),       # 同名第二张
            "c": _card("c", "Machete"),
        }
        errors = UnderworldSupport.validate_deck(["a", "b", "c"], db)
        assert errors == ["Lucky!"]

    def test_single_copies_legal(self):
        db = {"a": _card("a", "Lucky!"), "c": _card("c", "Machete")}
        assert UnderworldSupport.validate_deck(["a", "c"], db) == []

    def test_weakness_duplicates_exempt(self):
        db = {
            "w1": _card("w1", "Amnesia", subtype="basic_weakness"),
            "w2": _card("w2", "Amnesia", subtype="basic_weakness"),
        }
        assert UnderworldSupport.validate_deck(["w1", "w2"], db) == []

    def test_signature_duplicates_exempt(self):
        text = "Roland's .38 Special deck only."
        db = {
            "s1": _card("s1", "Roland's .38 Special", text=text),
            "s2": _card("s2", "Roland's .38 Special", text=text),
        }
        assert UnderworldSupport.validate_deck(["s1", "s2"], db) == []
