"""Tests for Ancient Stone (Level 1 & 4). (04022 / 04231)

lv1：[行动]调查+3隐蔽；成功额外发现1线索、丢弃并记录冒险日志（含括号难度）。
lv4：使用(X秘密)（X=lv1记录的难度）；抽牌时花费秘密治疗恐惧。
"""

import pytest

from backend.cards.seeker.ancient_stone_lv1 import (
    CAMPAIGN_LOG_ENTRY, DIFFICULTY_VAR, AncientStoneLv1,
)
from backend.cards.seeker.ancient_stone_lv4 import AncientStoneLv4
from backend.engine.game import Game
from backend.models.enums import Action, ChaosTokenType, GameEvent, Skill
from backend.engine.event_bus import EventContext
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_asset_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def game():
    g = Game("test_ancient_stone")
    g.chaos_bag.seed(42)
    inv_data = make_investigator_data(intellect=5)
    g.register_card_data(inv_data)
    loc_data = make_location_data(id="loc_a", shroud=2)
    g.register_card_data(loc_data)
    g.add_investigator("inv1", inv_data, starting_location="loc_a")
    g.add_location("loc_a", loc_data, clues=3)
    return g


def _place_stone(g, card_id, cls, uses=None):
    g.register_card_data(make_asset_data(id=card_id, traits=["item", "relic"]))
    inst = CardInstance(
        instance_id=f"inst_{card_id}", card_id=card_id,
        owner_id="inv1", controller_id="inv1",
    )
    if uses:
        inst.uses = dict(uses)
    g.state.cards_in_play[inst.instance_id] = inst
    inv = g.state.get_investigator("inv1")
    inv.play_area.append(inst.instance_id)
    impl = cls(inst.instance_id)
    impl.register(g.event_bus, inst.instance_id)
    return inst, impl


class TestAncientStoneLv1:
    def test_successful_investigation_full_flow(self, game):
        """完整流程：+3隐蔽、成功额外1线索、丢弃、冒险日志+括号难度。"""
        inv = game.state.get_investigator("inv1")
        loc = game.state.locations["loc_a"]
        inst, impl = _place_stone(game, "ancient_stone_lv1", AncientStoneLv1)
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]

        assert impl.activate(game.state, "inv1") is True
        assert game.action_resolver.perform_action("inv1", Action.INVESTIGATE)

        # 难度 2+3=5，智力5+0 → 恰好成功；基础1+额外1 = 2线索
        assert inv.clues == 2
        assert loc.clues == 1
        # 丢弃并记录
        assert inst.instance_id not in inv.play_area
        assert "ancient_stone_lv1" in inv.discard
        log = game.state.scenario.vars["campaign_log"]
        assert CAMPAIGN_LOG_ENTRY in log
        assert game.state.scenario.vars[DIFFICULTY_VAR] == 5

    def test_failed_investigation_keeps_stone(self, game):
        inv = game.state.get_investigator("inv1")
        inst, impl = _place_stone(game, "ancient_stone_lv1", AncientStoneLv1)
        game.chaos_bag.tokens = [ChaosTokenType.AUTO_FAIL]

        impl.activate(game.state, "inv1")
        game.action_resolver.perform_action("inv1", Action.INVESTIGATE)
        assert inv.clues == 0
        assert inst.instance_id in inv.play_area
        assert "campaign_log" not in game.state.scenario.vars


class TestAncientStoneLv4:
    def test_secrets_from_campaign_log_difficulty(self, game):
        """入场：秘密数=冒险日志括号中的难度。"""
        game.state.scenario.vars[DIFFICULTY_VAR] = 5
        inst, impl = _place_stone(game, "ancient_stone_lv4", AncientStoneLv4)
        game.event_bus.emit(EventContext(
            game_state=game.state, event=GameEvent.CARD_ENTERS_PLAY,
            investigator_id="inv1", target=inst.instance_id,
        ))
        assert inst.uses["secrets"] == 5

    def test_draw_spends_secret_to_heal_horror(self, game):
        """每抽1张牌：花费1秘密治疗1点恐惧。"""
        inv = game.state.get_investigator("inv1")
        inv.horror = 2
        inst, impl = _place_stone(game, "ancient_stone_lv4", AncientStoneLv4,
                                  uses={"secrets": 2})
        game.event_bus.emit(EventContext(
            game_state=game.state, event=GameEvent.CARD_DRAWN,
            investigator_id="inv1", extra={"card_id": "some_card"},
        ))
        assert inv.horror == 1
        assert inst.uses["secrets"] == 1

    def test_no_horror_no_spend(self, game):
        inv = game.state.get_investigator("inv1")
        inst, impl = _place_stone(game, "ancient_stone_lv4", AncientStoneLv4,
                                  uses={"secrets": 2})
        game.event_bus.emit(EventContext(
            game_state=game.state, event=GameEvent.CARD_DRAWN,
            investigator_id="inv1", extra={"card_id": "some_card"},
        ))
        assert inst.uses["secrets"] == 2  # 无可治疗恐惧：不花费
