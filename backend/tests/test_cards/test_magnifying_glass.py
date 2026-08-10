"""Tests for Magnifying Glass (Level 0)."""

import pytest
from backend.cards.seeker.magnifying_glass_lv0 import MagnifyingGlass
from backend.engine.game import Game
from backend.models.enums import Action, CardType, ChaosTokenType, PlayerClass, SlotType
from backend.models.state import CardData, CardInstance
from backend.tests.conftest import make_investigator_data, make_location_data


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data(intellect=3)
    g.register_card_data(inv_data)

    loc = make_location_data(shroud=3, clue_value=3)
    g.register_card_data(loc)

    mag_data = CardData(
        id="magnifying_glass_lv0", name="Magnifying Glass", name_cn="放大镜",
        type=CardType.ASSET, card_class=PlayerClass.SEEKER, cost=1,
        slots=[SlotType.HAND], skill_icons={"intellect": 1},
    )
    g.register_card_data(mag_data)

    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=3)

    g.card_registry.register_class(MagnifyingGlass)
    return g


def _equip_mag_glass(game):
    inv = game.state.get_investigator("inv1")
    instance_id = game.state.next_instance_id()
    card_inst = CardInstance(
        instance_id=instance_id, card_id="magnifying_glass_lv0",
        owner_id="inv1", controller_id="inv1",
        slot_used=[SlotType.HAND],
    )
    game.state.cards_in_play[instance_id] = card_inst
    inv.play_area.append(instance_id)
    game.card_registry.activate_card("magnifying_glass_lv0", instance_id, game.event_bus)
    return instance_id


class TestMagnifyingGlass:
    def test_card_registered(self, game):
        assert "magnifying_glass_lv0" in game.card_registry.registered_cards

    def test_intellect_bonus_helps_investigate(self, game):
        """Magnifying Glass +1 intellect helps pass investigate test."""
        _equip_mag_glass(game)
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]

        inv = game.state.get_investigator("inv1")
        inv.actions_remaining = 3

        # Intellect 3 + 1 mag glass = 4 >= shroud 3 -> success
        game.action_resolver.perform_action("inv1", Action.INVESTIGATE)
        assert inv.clues == 1

    def test_without_mag_glass_harder(self, game):
        """Without Magnifying Glass, same test with -1 token fails."""
        game.chaos_bag.tokens = [ChaosTokenType.MINUS_1]

        inv = game.state.get_investigator("inv1")
        inv.actions_remaining = 3

        # Intellect 3 + (-1) = 2 < shroud 3 -> fail
        game.action_resolver.perform_action("inv1", Action.INVESTIGATE)
        assert inv.clues == 0

    def test_asset_bonus_recorded_in_result(self, game):
        """asset_bonus/skill_bonus_sources 记录在检定结果中（供 UI 展示）。"""
        _equip_mag_glass(game)
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]

        captured = {}

        def on_success(result):
            captured["result"] = result

        # 放大镜只在"调查时"提供加值：先标记调查行动
        from backend.engine.event_bus import EventContext
        from backend.models.enums import GameEvent
        game.event_bus.emit(EventContext(
            game_state=game.state,
            event=GameEvent.INVESTIGATE_ACTION_INITIATED,
            investigator_id="inv1",
        ))
        game.skill_test_engine.run_test(
            investigator_id="inv1",
            skill_type=__import__("backend.models.enums", fromlist=["Skill"]).Skill.INTELLECT,
            difficulty=3,
            committed_card_ids=[],
            on_success=on_success,
        )
        result = captured["result"]
        assert result.extra["asset_bonus"] == 1
        assert any(
            s["reason"] == "magnifying_glass_bonus" and s["delta"] == 1
            for s in result.extra["skill_bonus_sources"]
        )

    def test_no_bonus_when_not_investigating(self, game):
        """非调查的智力检定（如诡计卡检定）不享受放大镜加值。"""
        _equip_mag_glass(game)
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]

        result = game.skill_test_engine.run_test(
            investigator_id="inv1",
            skill_type=__import__("backend.models.enums", fromlist=["Skill"]).Skill.INTELLECT,
            difficulty=4,
            committed_card_ids=[],
        )
        # int 3 + 0 = 3 < 4 -> fail（无 +1）
        assert not result.success
        assert result.extra["asset_bonus"] == 0

    def test_preview_skill_bonuses(self, game):
        """preview_skill_bonuses 是无上下文的干跑；放大镜的"调查时"条件
        加值不在预览中出现（与 dr_milan 的无条件 +1 智力不同）。"""
        assert game.preview_skill_bonuses("inv1") == {}
        _equip_mag_glass(game)
        assert game.preview_skill_bonuses("inv1") == {}
        # 真实调查仍能获得加值
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]
        inv = game.state.get_investigator("inv1")
        inv.actions_remaining = 3
        game.action_resolver.perform_action("inv1", Action.INVESTIGATE)
        assert inv.clues == 1
