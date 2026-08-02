"""Regression tests: Mind over Matter, encounter deck location leak, dunwich treacheries."""

import pytest

from backend.engine.game import Game
from backend.models.enums import Action, Skill
from backend.models.state import CardInstance
from backend.scenarios.official_core import (
    ScenarioController,
    apply_scenario_to_game,
    load_encounter_db_for_campaign,
)
from backend.tests.conftest import (
    make_enemy_data,
    make_investigator_data,
    make_location_data,
)
from server.game_session import _load_player_cards


class TestMindOverMatter:
    """Regression: MoM used getattr(inv, 'intellect', 0) which always yielded 0
    (skill values live on card_data.skills), making the card a no-op."""

    def _game(self):
        g = Game("test")
        g.chaos_bag.seed(42)  # deterministic tokens (avoid autofail flakiness)
        inv_data = make_investigator_data()
        inv_data.skills.combat = 2
        inv_data.skills.intellect = 5
        g.register_card_data(inv_data)
        loc = make_location_data()
        g.register_card_data(loc)
        g.add_investigator("p", inv_data, starting_location="test_location",
                           deck=["mind_over_matter_lv0"] * 3)
        g.add_location("test_location", loc)
        _load_player_cards(g)

        ed = make_enemy_data()
        ed.enemy_fight = 4
        ed.enemy_health = 5
        g.register_card_data(ed)
        g.state.cards_in_play["e1"] = CardInstance(
            instance_id="e1", card_id="test_enemy",
            owner_id="s", controller_id="s")
        g.state.get_investigator("p").threat_area.append("e1")
        g.setup()
        inv = g.state.get_investigator("p")
        inv.actions_remaining = 10
        return g

    def test_fight_uses_intellect_after_play(self):
        g = self._game()
        ok = g.action_resolver.perform_action("p", Action.PLAY, card_id="mind_over_matter_lv0")
        assert ok is True

        g.action_resolver.perform_action("p", Action.FIGHT, enemy_instance_id="e1")
        result = g.skill_test_engine._last_result
        # 智力5 替换 战斗2（token 修正另算）
        assert result.modified_skill >= 5 - 5  # 下限防呆
        assert result.base_skill == 2
        # 标记修正为0时应该正好等于智力
        assert result.modified_skill == 5 + result.token_modifier + result.committed_icons

    def test_no_substitution_without_play(self):
        g = self._game()
        g.action_resolver.perform_action("p", Action.FIGHT, enemy_instance_id="e1")
        result = g.skill_test_engine._last_result
        assert result.modified_skill == 2 + result.token_modifier + result.committed_icons


class TestEncounterDeckNoLocationLeak:
    """Location cards (incl. _b variants) must never enter the encounter deck."""

    @pytest.mark.parametrize("sid", [
        "extracurricular_activity", "the_miskatonic_museum", "essex_county_express",
        "blood_on_the_altar", "undimensioned_and_unseen", "where_doom_awaits",
    ])
    def test_no_location_cards_in_deck(self, sid):
        g = Game(sid)
        apply_scenario_to_game(g, sid, seed=42)
        db = load_encounter_db_for_campaign("dunwich_legacy")
        for cid in g.state.scenario.encounter_deck:
            rec = db.get(cid, {})
            assert rec.get("type") != "location", f"{sid}: 地点卡 {cid} 泄漏进遭遇堆"


class TestDunwichTreacheries:
    def _game_with_controller(self):
        g = Game("extracurricular_activity")
        g.chaos_bag.seed(42)
        inv_data = make_investigator_data()
        g.register_card_data(inv_data)
        loc = make_location_data()
        g.register_card_data(loc)
        g.add_investigator("player", inv_data, deck=[f"c{i}" for i in range(20)],
                           starting_location="test_location")
        g.add_location("test_location", loc)
        g.setup()
        ctrl = ScenarioController(g, action_log=[])
        return g, ctrl

    def test_across_space_and_time_discards_top3(self):
        from backend.scenarios.dunwich_encounters import resolve_dunwich_treachery
        g, ctrl = self._game_with_controller()
        inv = g.state.get_investigator("player")
        deck_before = list(inv.deck)

        res = resolve_dunwich_treachery(ctrl, "across_space_and_time", investigator_id="player")
        assert res is not None
        assert inv.discard == deck_before[:3]
        assert inv.deck == deck_before[3:]

    def test_eager_for_death_difficulty_scales_with_damage(self):
        from backend.scenarios.dunwich_encounters import resolve_dunwich_treachery
        g, ctrl = self._game_with_controller()
        inv = g.state.get_investigator("player")
        inv.damage = 3
        g.chaos_bag.tokens = []  # 空袋 → 跑测试时给固定标记
        from backend.models.enums import ChaosTokenType
        g.chaos_bag.tokens = [ChaosTokenType.MINUS_8]

        resolve_dunwich_treachery(ctrl, "eager_for_death", investigator_id="player")
        result = g.skill_test_engine._last_result
        assert result.difficulty == 5  # 2 + 3伤害
        assert inv.horror == 2  # 失败 → 2恐惧

    def test_unhandled_returns_none(self):
        from backend.scenarios.dunwich_encounters import resolve_dunwich_treachery
        g, ctrl = self._game_with_controller()
        assert resolve_dunwich_treachery(ctrl, "nonexistent_card", investigator_id="player") is None
