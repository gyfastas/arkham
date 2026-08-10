"""Tests for Gang Up (Level 1). (08022)

攻击。你控制的卡牌中每有一种不同阵营，本次攻击+1战斗/+1伤害。
"""

import pytest
from backend.cards.guardian.gang_up_lv1 import GangUp
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import (
    Action, CardType, ChaosTokenType, GameEvent, PlayerClass,
)
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_asset_data, make_enemy_data, make_event_data,
    make_investigator_data, make_location_data,
)


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)
    inv_data = make_investigator_data(combat=3)
    g.register_card_data(inv_data)
    g.register_card_data(make_location_data())
    g.register_card_data(make_event_data(
        id="gang_up_lv1", name="Gang Up", cost=3,
        card_class=PlayerClass.GUARDIAN,
    ))
    g.register_card_data(make_enemy_data(fight=3, health=10))
    # 两张不同阵营的场上支援
    g.register_card_data(make_asset_data(
        id="guardian_asset", name="G", card_class=PlayerClass.GUARDIAN))
    g.register_card_data(make_asset_data(
        id="seeker_asset", name="S", card_class=PlayerClass.SEEKER))
    g.register_card_data(make_asset_data(
        id="seeker_asset_2", name="S2", card_class=PlayerClass.SEEKER))

    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", g.state.get_card_data("test_location"), clues=0)
    g.card_registry.register_class(GangUp)

    game = g
    inv = game.state.get_investigator("inv1")
    for i, cid in enumerate(("guardian_asset", "seeker_asset", "seeker_asset_2")):
        iid = f"asset_{i}"
        game.state.cards_in_play[iid] = CardInstance(
            instance_id=iid, card_id=cid, owner_id="inv1", controller_id="inv1",
        )
        inv.play_area.append(iid)
    game.state.cards_in_play["enemy_1"] = CardInstance(
        instance_id="enemy_1", card_id="test_enemy",
        owner_id="scenario", controller_id="scenario",
    )
    inv.threat_area.append("enemy_1")
    inv.actions_remaining = 3
    inv.hand.append("gang_up_lv1")
    return g


def _play(game):
    impl = game.card_registry.activate_card("gang_up_lv1", "gu_1", game.event_bus)
    ctx = EventContext(
        game_state=game.state, event=GameEvent.CARD_PLAYED,
        investigator_id="inv1", extra={"card_id": "gang_up_lv1"},
    )
    game.event_bus.emit(ctx)
    inv = game.state.get_investigator("inv1")
    inv.hand.remove("gang_up_lv1")
    inv.discard.append("gang_up_lv1")
    return ctx, impl


class TestGangUp:
    def test_bonus_per_class(self, game):
        """2种不同阵营（guardian+seeker）：+2战斗/+2伤害。"""
        ctx, _ = _play(game)
        assert ctx.extra["gang_up_classes"] == 2
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]

        game.action_resolver.perform_action(
            "inv1", Action.FIGHT, enemy_instance_id="enemy_1",
        )
        # 战斗 3+2+0=5 vs 3 → 成功，伤害 1+2=3
        assert game.state.get_card_instance("enemy_1").damage == 3

    def test_no_assets_no_bonus(self, game):
        """场上无支援：0阵营，无加值。"""
        inv = game.state.get_investigator("inv1")
        for iid in ("asset_0", "asset_1", "asset_2"):
            inv.play_area.remove(iid)
            game.state.cards_in_play.pop(iid)

        ctx, _ = _play(game)
        assert ctx.extra["gang_up_classes"] == 0
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]

        game.action_resolver.perform_action(
            "inv1", Action.FIGHT, enemy_instance_id="enemy_1",
        )
        assert game.state.get_card_instance("enemy_1").damage == 1
