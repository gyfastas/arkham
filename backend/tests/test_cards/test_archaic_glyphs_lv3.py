"""Tests for Archaic Glyphs (Guiding Stones, Level 3) and
Archaic Glyphs (Prophecy Foretold, Level 3).

Guiding Stones：[行动]花1充能：调查；每超出难度2点额外发现1条线索。
Prophecy Foretold：[行动]花1充能：调查；成功则自动躲避1个交战敌人。
"""

import pytest

from backend.cards.seeker.archaic_glyphs_guiding_stones_lv3 import (
    ArchaicGlyphsGuidingStones,
)
from backend.cards.seeker.archaic_glyphs_prophecy_foretold_lv3 import (
    ArchaicGlyphsProphecyForetold,
)
from backend.engine.game import Game
from backend.models.enums import ChaosTokenType
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_asset_data, make_enemy_data, make_investigator_data,
    make_location_data,
)


def _make_game(card_id, impl_cls, with_enemy=False):
    g = Game(f"test_{card_id}")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data(intellect=5)
    g.register_card_data(inv_data)
    loc_data = make_location_data(id="loc_a", shroud=2, clue_value=3)
    g.register_card_data(loc_data)
    g.add_investigator("player", inv_data, starting_location="loc_a")
    g.add_location("loc_a", loc_data, clues=3)

    g.register_card_data(make_asset_data(
        id=card_id, name="Archaic Glyphs", cost=2,
        uses={"charges": 3}, traits=["spell"],
    ))
    inst = CardInstance(
        instance_id="inst_glyphs", card_id=card_id,
        owner_id="player", controller_id="player",
    )
    inst.uses = {"charges": 3}
    g.state.cards_in_play["inst_glyphs"] = inst
    g.state.get_investigator("player").play_area.append("inst_glyphs")

    impl = impl_cls("inst_glyphs")
    impl.register(g.event_bus, "inst_glyphs")
    impl.bind_chaos_bag(g.chaos_bag)

    if with_enemy:
        enemy_data = make_enemy_data(id="cultist", name="Cultist")
        g.register_card_data(enemy_data)
        g.state.cards_in_play["enemy_1"] = CardInstance(
            instance_id="enemy_1", card_id="cultist",
            owner_id="scenario", controller_id="scenario",
        )
        g.state.get_investigator("player").threat_area.append("enemy_1")
    return g, impl


class TestGuidingStones:
    def test_success_discovers_bonus_clues(self):
        """智力5 vs 隐蔽2，+0标记：超难度3点 → 基础1 + 额外1 = 2条线索。"""
        g, impl = _make_game("archaic_glyphs_guiding_stones_lv3",
                             ArchaicGlyphsGuidingStones)
        g.chaos_bag.tokens = [ChaosTokenType.ZERO]
        assert impl.activate(g.state, "player") is True

        inv = g.state.get_investigator("player")
        loc = g.state.get_location("loc_a")
        assert inv.clues == 2
        assert loc.clues == 1
        inst = g.state.get_card_instance("inst_glyphs")
        assert inst.uses["charges"] == 2

    def test_failure_discovers_nothing(self):
        g, impl = _make_game("archaic_glyphs_guiding_stones_lv3",
                             ArchaicGlyphsGuidingStones)
        g.chaos_bag.tokens = [ChaosTokenType.MINUS_5]  # 5-5=0 < 2
        assert impl.activate(g.state, "player") is True

        inv = g.state.get_investigator("player")
        loc = g.state.get_location("loc_a")
        assert inv.clues == 0
        assert loc.clues == 3

    def test_no_charges_cannot_activate(self):
        g, impl = _make_game("archaic_glyphs_guiding_stones_lv3",
                             ArchaicGlyphsGuidingStones)
        inst = g.state.get_card_instance("inst_glyphs")
        inst.uses["charges"] = 0
        assert impl.activate(g.state, "player") is False


class TestProphecyForetold:
    def test_success_auto_evades_engaged_enemy(self):
        """调查成功：发现1条线索并自动躲避交战敌人。"""
        g, impl = _make_game("archaic_glyphs_prophecy_foretold_lv3",
                             ArchaicGlyphsProphecyForetold, with_enemy=True)
        g.chaos_bag.tokens = [ChaosTokenType.ZERO]
        assert impl.activate(g.state, "player") is True

        inv = g.state.get_investigator("player")
        loc = g.state.get_location("loc_a")
        assert inv.clues == 1
        assert loc.clues == 2
        enemy = g.state.get_card_instance("enemy_1")
        assert enemy.exhausted is True
        assert "enemy_1" not in inv.threat_area
        assert "enemy_1" in loc.enemies

    def test_failure_no_evade(self):
        g, impl = _make_game("archaic_glyphs_prophecy_foretold_lv3",
                             ArchaicGlyphsProphecyForetold, with_enemy=True)
        g.chaos_bag.tokens = [ChaosTokenType.AUTO_FAIL]
        assert impl.activate(g.state, "player") is True

        inv = g.state.get_investigator("player")
        enemy = g.state.get_card_instance("enemy_1")
        assert inv.clues == 0
        assert enemy.exhausted is False
        assert "enemy_1" in inv.threat_area
