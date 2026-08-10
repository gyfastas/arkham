"""Tests for Mark Harrigan investigator ability."""

import pytest
from backend.cards.guardian.mark_harrigan import MarkHarrigan
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import ChaosTokenType, GameEvent
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_asset_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def game():
    g = Game("test_mark")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data(id="mark_harrigan", name="Mark Harrigan")
    g.register_card_data(inv_data)

    loc_data = make_location_data()
    g.register_card_data(loc_data)

    deck = ["card_a", "card_b", "card_c", "card_d", "card_e"] * 3
    g.add_investigator("mark", inv_data, deck=deck, starting_location="test_location")
    g.add_location("test_location", loc_data, clues=3)

    return g


@pytest.fixture
def impl(game):
    impl = MarkHarrigan("test_instance")
    impl.register(game.event_bus, "test_instance")
    return impl


def _emit(game, event, **kwargs):
    ctx = EventContext(game_state=game.state, event=event, **kwargs)
    game.event_bus.emit(ctx)
    return ctx


class TestSophieSetup:
    def test_setup_sophie_places_sophie_idempotent(self, game, impl):
        """setup_sophie() 将索菲放置入场，且幂等。"""
        inst_id = impl.setup_sophie(game.state, "mark")
        assert inst_id is not None

        inv = game.state.get_investigator("mark")
        assert inst_id in inv.play_area
        inst = game.state.get_card_instance(inst_id)
        assert inst is not None and inst.card_id == "sophie_lv0"

        again = impl.setup_sophie(game.state, "mark")
        assert again == inst_id
        assert len(inv.play_area) == 1

    def test_round_begins_fallback_places_sophie(self, game, impl):
        """第一轮开始时若索菲未入场则兜底入场（之后不重复）。"""
        _emit(game, GameEvent.ROUND_BEGINS)
        inv = game.state.get_investigator("mark")
        assert len(inv.play_area) == 1
        inst = game.state.get_card_instance(inv.play_area[0])
        assert inst.card_id == "sophie_lv0"

        _emit(game, GameEvent.ROUND_BEGINS)
        assert len(inv.play_area) == 1

    def test_setup_sophie_ignores_other_investigators(self, game, impl):
        """setup_sophie 对其他调查员无效。"""
        other_data = make_investigator_data(id="other_inv", name="Other")
        game.register_card_data(other_data)
        game.add_investigator("other", other_data, deck=[], starting_location="test_location")

        assert impl.setup_sophie(game.state, "other") is None
        assert game.state.get_investigator("other").play_area == []


class TestDrawOnDamage:
    def test_damage_on_mark_draws_card_once_per_phase(self, game, impl):
        """马克被放置伤害后抽1张；每阶段限1次，阶段切换后重置。"""
        inv = game.state.get_investigator("mark")
        hand_before = len(inv.hand)

        game.damage_engine.deal_damage("mark", damage=1)
        assert len(inv.hand) == hand_before + 1

        # 同一阶段再次受伤：不再抽
        game.damage_engine.deal_damage("mark", damage=2)
        assert len(inv.hand) == hand_before + 1

        # 新阶段开始：限次重置
        _emit(game, GameEvent.INVESTIGATION_PHASE_BEGINS)
        game.damage_engine.deal_damage("mark", damage=1)
        assert len(inv.hand) == hand_before + 2

    def test_damage_soaked_by_controlled_asset_still_draws(self, game, impl):
        """伤害分配到马克控制的支援卡上同样触发抽牌。"""
        ally_data = make_asset_data(id="ally_lv0", name="Ally", health=2, sanity=2)
        game.register_card_data(ally_data)
        game.state.cards_in_play["ally_1"] = CardInstance(
            instance_id="ally_1", card_id="ally_lv0",
            owner_id="mark", controller_id="mark",
        )
        inv = game.state.get_investigator("mark")
        inv.play_area.append("ally_1")
        hand_before = len(inv.hand)

        game.damage_engine.deal_damage(
            "mark", damage=1, damage_assignment={"ally_1": 1},
        )
        ally = game.state.get_card_instance("ally_1")
        assert ally.damage == 1
        assert inv.damage == 0
        assert len(inv.hand) == hand_before + 1

    def test_no_draw_for_other_investigators(self, game, impl):
        """其他调查员被放置伤害时马克不抽牌。"""
        other_data = make_investigator_data(id="other_inv", name="Other")
        game.register_card_data(other_data)
        game.add_investigator("other", other_data, deck=["x"] * 5,
                              starting_location="test_location")

        inv = game.state.get_investigator("mark")
        hand_before = len(inv.hand)
        game.damage_engine.deal_damage("other", damage=1)
        assert len(inv.hand) == hand_before


class TestElderSign:
    def test_elder_sign_bonus_per_damage(self, game, impl):
        """远古印记：马克身上每有1点伤害 +1。"""
        inv = game.state.get_investigator("mark")
        inv.damage = 3

        ctx = _emit(
            game, GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="mark", chaos_token=ChaosTokenType.ELDER_SIGN,
        )
        assert ctx.amount == 3

    def test_elder_sign_no_damage_no_bonus(self, game, impl):
        """无伤害时远古印记 +0；非远古印记标记不触发。"""
        ctx = _emit(
            game, GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="mark", chaos_token=ChaosTokenType.ELDER_SIGN,
        )
        assert ctx.amount == 0

        inv = game.state.get_investigator("mark")
        inv.damage = 3
        ctx = _emit(
            game, GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="mark", chaos_token=ChaosTokenType.SKULL,
        )
        assert ctx.amount == 0
