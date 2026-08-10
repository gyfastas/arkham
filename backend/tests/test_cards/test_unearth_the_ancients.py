"""Tests for Unearth the Ancients (Level 0 / Level 2).

官方 lv0：调查。选择手牌1张[seeker]支援卡，检定难度=其打印费用；成功
则不发现线索，改为将其放置入场；若为[[遗物]]，抽1张牌。
官方 lv2：选最多2张，难度=费用之和；成功依次入场；每张遗物抽1张牌。
"""

import pytest

from backend.cards.seeker.unearth_the_ancients_lv0 import UnearthTheAncients
from backend.cards.seeker.unearth_the_ancients_lv2 import UnearthTheAncientsLv2
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import CardType, ChaosTokenType, GameEvent, PlayerClass
from backend.models.state import CardData
from backend.tests.conftest import (
    make_investigator_data, make_location_data,
)


def _seeker_asset(card_id, name, cost, traits=(), slots=()):
    return CardData(
        id=card_id, name=name, name_cn=name, type=CardType.ASSET,
        card_class=PlayerClass.SEEKER, cost=cost, traits=list(traits),
        slots=list(slots),
    )


def _make_game(card_id, impl_cls, hand, deck=None):
    g = Game(f"test_{card_id}")
    g.chaos_bag.seed(42)
    g.chaos_bag.tokens = [ChaosTokenType.ZERO]

    inv_data = make_investigator_data(intellect=5)
    g.register_card_data(inv_data)
    loc_data = make_location_data(id="loc_a", shroud=2)
    g.register_card_data(loc_data)
    g.add_investigator(
        "player", inv_data, deck=deck or [], starting_location="loc_a")
    g.add_location("loc_a", loc_data, clues=2)
    inv = g.state.get_investigator("player")
    inv.hand = list(hand)

    g.register_card_data(_seeker_asset(
        "tooth_of_eztli_lv0", "Tooth of Eztli", 3, traits=["item", "relic"]))
    g.register_card_data(_seeker_asset(
        "magnifying_glass_lv0", "Magnifying Glass", 2, traits=["item", "tool"]))
    g.register_card_data(CardData(
        id="guardian_asset", name="Beat Cop", name_cn="巡警",
        type=CardType.ASSET, card_class=PlayerClass.GUARDIAN, cost=4,
    ))
    g.register_card_data(make_investigator_data(id="irrelevant"))
    g.register_card_data(CardData(
        id=card_id, name="Unearth the Ancients", name_cn="发掘古物",
        type=CardType.EVENT, card_class=PlayerClass.SEEKER, cost=1,
    ))
    g.card_registry.register_class(impl_cls)
    g.card_registry.activate_card(
        card_id, "impl_uta", g.event_bus, chaos_bag=g.chaos_bag)
    return g


def _play(game, card_id, **extra):
    ctx = EventContext(
        game_state=game.state, event=GameEvent.CARD_PLAYED,
        investigator_id="player",
        extra={"card_id": card_id, **extra},
    )
    game.event_bus.emit(ctx)
    return ctx


class TestUnearthTheAncientsLv0:
    def test_success_puts_asset_into_play_and_draws_for_relic(self):
        """成功：遗物（费用3，难度3）免费入场并抽1张牌。"""
        g = _make_game(
            "unearth_the_ancients_lv0", UnearthTheAncients,
            hand=["tooth_of_eztli_lv0", "magnifying_glass_lv0"],
            deck=["card_a"],
        )
        inv = g.state.get_investigator("player")
        # 自动选择费用最高的 seeker 支援：埃兹特里之牙(3)
        ctx = _play(g, "unearth_the_ancients_lv0")
        assert ctx.extra.get("unearth_the_ancients_success") is True
        assert ctx.extra.get("unearth_the_ancients_played") == ["tooth_of_eztli_lv0"]
        assert ctx.extra.get("unearth_the_ancients_relics") == 1
        assert "tooth_of_eztli_lv0" not in inv.hand
        assert any(
            (ci := g.state.get_card_instance(iid)) is not None
            and ci.card_id == "tooth_of_eztli_lv0"
            for iid in inv.play_area
        )
        assert "card_a" in inv.hand  # 遗物：抽1张
        # 不发现线索
        assert g.state.get_location("loc_a").clues == 2
        assert inv.clues == 0

    def test_failure_nothing_enters(self):
        g = _make_game(
            "unearth_the_ancients_lv0", UnearthTheAncients,
            hand=["tooth_of_eztli_lv0"],
        )
        g.chaos_bag.tokens = [ChaosTokenType.AUTO_FAIL]
        inv = g.state.get_investigator("player")
        ctx = _play(g, "unearth_the_ancients_lv0")
        assert ctx.extra.get("unearth_the_ancients_success") is False
        assert "tooth_of_eztli_lv0" in inv.hand
        assert inv.play_area == []

    def test_no_seeker_asset_no_effect(self):
        g = _make_game(
            "unearth_the_ancients_lv0", UnearthTheAncients,
            hand=["guardian_asset"],
        )
        ctx = _play(g, "unearth_the_ancients_lv0")
        assert ctx.extra.get("unearth_the_ancients_failed") == "no_asset"


class TestUnearthTheAncientsLv2:
    def test_two_assets_combined_cost_and_relic_draws(self):
        """选2张（费用3+2=5，难度5），智力5成功：两张入场，遗物抽1张。"""
        g = _make_game(
            "unearth_the_ancients_lv2", UnearthTheAncientsLv2,
            hand=["tooth_of_eztli_lv0", "magnifying_glass_lv0"],
            deck=["card_a"],
        )
        inv = g.state.get_investigator("player")
        ctx = _play(g, "unearth_the_ancients_lv2")
        assert ctx.extra.get("unearth_the_ancients_success") is True
        assert sorted(ctx.extra.get("unearth_the_ancients_played")) == [
            "magnifying_glass_lv0", "tooth_of_eztli_lv0"]
        assert ctx.extra.get("unearth_the_ancients_relics") == 1
        assert inv.hand == ["card_a"]  # 两张都入场，仅遗物抽1张
        assert len(inv.play_area) == 2
