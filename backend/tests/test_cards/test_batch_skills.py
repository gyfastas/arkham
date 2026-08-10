"""Tests for Self-Sacrifice, Steadfast, Take the Initiative (skills).

自我牺牲(06157)：投入同地点他人检定；失败则失败效果改由你结算（标记），你抽2张。
坚定不移(05022)：剩余生命+神智≥5 追加1图标，≥10 追加2（意志/战斗检定）。
占据先机(04150)：3通用图标；本阶段每完成1个行动失去1个。
"""

import pytest

from backend.cards.guardian.self_sacrifice_lv0 import SelfSacrifice
from backend.cards.guardian.steadfast_lv0 import Steadfast
from backend.cards.guardian.take_the_initiative_lv0 import TakeTheInitiative
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import (
    ChaosTokenType, GameEvent, Skill,
)
from backend.tests.conftest import (
    make_investigator_data, make_location_data, make_skill_data,
)


def _game(two_invs=False):
    g = Game("test")
    g.chaos_bag.seed(42)
    inv_data = make_investigator_data(willpower=3)
    g.register_card_data(inv_data)
    loc = make_location_data()
    g.register_card_data(loc)
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", g.state.get_card_data("test_location"))
    if two_invs:
        g.add_investigator("inv2", inv_data, starting_location="test_location")
    return g


class TestSelfSacrifice:
    def test_failed_test_redirects_and_draws(self):
        """他人检定失败：重定向标记指向投入者，投入者抽2张牌。"""
        game = _game(two_invs=True)
        game.register_card_data(make_skill_data(
            id="self_sacrifice_lv0", name="Self-Sacrifice", skill_icons={},
        ))
        game.card_registry.register_class(SelfSacrifice)
        game.chaos_bag.tokens = [ChaosTokenType.MINUS_3]

        owner = game.state.get_investigator("inv2")
        owner.hand.append("self_sacrifice_lv0")
        owner.deck = ["c1", "c2", "c3"]
        hand_before = len(owner.hand)

        result = game.skill_test_engine.run_test(
            "inv1", Skill.WILLPOWER, difficulty=9,
            committed_card_ids=["self_sacrifice_lv0"],
        )
        assert result.success is False
        redirect = game.state.scenario.vars.get("self_sacrifice_redirect")
        assert redirect == {"from": "inv1", "to": "inv2"}
        assert result.extra.get("self_sacrifice_redirect") == "inv2"
        # 投入者抽2张（卡面：你或执行者抽2张，简化为投入者）
        assert len(owner.hand) == hand_before + 2

    def test_no_effect_when_not_committed(self):
        """未投入本卡：无重定向标记。"""
        game = _game(two_invs=True)
        game.card_registry.register_class(SelfSacrifice)
        game.chaos_bag.tokens = [ChaosTokenType.MINUS_3]

        result = game.skill_test_engine.run_test(
            "inv1", Skill.WILLPOWER, difficulty=9,
        )
        assert result.success is False
        assert "self_sacrifice_redirect" not in game.state.scenario.vars


class TestSteadfast:
    def _setup(self, game):
        game.register_card_data(make_skill_data(
            id="steadfast_lv0", name="Steadfast",
            skill_icons={"willpower": 1, "combat": 1},
        ))
        game.card_registry.register_class(Steadfast)
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]

    def test_full_health_grants_2_bonus_icons(self):
        """剩余生命+神智=14（≥10）：意志检定 印刷1 + 条件2 = 3图标。"""
        game = _game()
        self._setup(game)
        result = game.skill_test_engine.run_test(
            "inv1", Skill.WILLPOWER, difficulty=9,
            committed_card_ids=["steadfast_lv0"],
        )
        assert result.committed_icons == 3

    def test_five_remaining_grants_1_bonus_icon(self):
        """剩余合计9（≥5且<10）：印刷1 + 条件1 = 2图标。"""
        game = _game()
        self._setup(game)
        game.state.get_investigator("inv1").damage = 5  # 余2生命+7神智=9
        result = game.skill_test_engine.run_test(
            "inv1", Skill.WILLPOWER, difficulty=9,
            committed_card_ids=["steadfast_lv0"],
        )
        assert result.committed_icons == 2

    def test_below_five_grants_nothing(self):
        """剩余合计4（<5）：仅印刷1图标。"""
        game = _game()
        self._setup(game)
        inv = game.state.get_investigator("inv1")
        inv.damage = 5  # 余2生命
        inv.horror = 5  # 余2神智，合计4
        result = game.skill_test_engine.run_test(
            "inv1", Skill.WILLPOWER, difficulty=9,
            committed_card_ids=["steadfast_lv0"],
        )
        assert result.committed_icons == 1

    def test_combat_test_also_benefits(self):
        """战斗检定同样享受条件图标。"""
        game = _game()
        self._setup(game)
        result = game.skill_test_engine.run_test(
            "inv1", Skill.COMBAT, difficulty=9,
            committed_card_ids=["steadfast_lv0"],
        )
        assert result.committed_icons == 3


class TestTakeTheInitiative:
    def _setup(self, game):
        game.register_card_data(make_skill_data(
            id="take_the_initiative_lv0", name="Take the Initiative",
            skill_icons={"wild": 3},
        ))
        game.card_registry.register_class(TakeTheInitiative)
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]
        # 手牌持续实例：跟踪本阶段行动数
        tracker = TakeTheInitiative("tti_hand")
        tracker.register(game.event_bus, "tti_hand")

    def test_full_icons_as_first_action(self):
        """本阶段无已完成行动：3通用图标全保留。"""
        game = _game()
        self._setup(game)
        result = game.skill_test_engine.run_test(
            "inv1", Skill.AGILITY, difficulty=9,
            committed_card_ids=["take_the_initiative_lv0"],
        )
        assert result.committed_icons == 3

    def test_icons_decay_with_actions(self):
        """本阶段已完成2个行动：3-2=1图标。"""
        game = _game()
        self._setup(game)
        for _ in range(2):
            game.event_bus.emit(EventContext(
                game_state=game.state, event=GameEvent.ACTION_PERFORMED,
                investigator_id="inv1",
            ))
        result = game.skill_test_engine.run_test(
            "inv1", Skill.AGILITY, difficulty=9,
            committed_card_ids=["take_the_initiative_lv0"],
        )
        assert result.committed_icons == 1

    def test_decay_capped_at_3_and_resets_each_phase(self):
        """超过3个行动最多失去3个；新阶段开始清零。"""
        game = _game()
        self._setup(game)
        for _ in range(5):
            game.event_bus.emit(EventContext(
                game_state=game.state, event=GameEvent.ACTION_PERFORMED,
                investigator_id="inv1",
            ))
        result = game.skill_test_engine.run_test(
            "inv1", Skill.AGILITY, difficulty=9,
            committed_card_ids=["take_the_initiative_lv0"],
        )
        assert result.committed_icons == 0

        game.event_bus.emit(EventContext(
            game_state=game.state, event=GameEvent.INVESTIGATION_PHASE_BEGINS,
        ))
        result = game.skill_test_engine.run_test(
            "inv1", Skill.AGILITY, difficulty=9,
            committed_card_ids=["take_the_initiative_lv0"],
        )
        assert result.committed_icons == 3
