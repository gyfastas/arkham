"""Tests for generic player card implementations (batch 4)."""

import pytest

from backend.cards.guardian.blackjack_lv0 import Blackjack
from backend.cards.guardian.taunt_lv0 import Taunt
from backend.cards.guardian.taunt_lv2 import TauntLv2
from backend.cards.guardian.teamwork_lv0 import Teamwork
from backend.cards.mystic.bind_monster_lv2 import BindMonster
from backend.cards.neutral.kukri_lv0 import Kukri
from backend.cards.neutral.search_for_the_truth_lv0 import SearchForTheTruth
from backend.cards.rogue.double_or_nothing_lv0 import DoubleOrNothing
from backend.cards.rogue.hired_muscle_lv1 import HiredMuscle
from backend.cards.rogue.think_on_your_feet_lv0 import ThinkOnYourFeet
from backend.cards.seeker.crack_the_case_lv0 import CrackTheCase
from backend.cards.seeker.preposterous_sketches_lv2 import PreposterousSketchesLv2
from backend.cards.seeker.strange_solution_lv0 import StrangeSolution
from backend.cards.survivor.bait_and_switch_lv0 import BaitAndSwitch
from backend.cards.survivor.peter_sylvestre_lv2 import PeterSylvestreLv2
from backend.engine.event_bus import EventContext
from backend.models.enums import GameEvent, Skill
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_enemy_data,
    make_investigator_data,
    make_location_data,
)


def _emit(game, event, inv_id="test_investigator", **kwargs):
    ctx = EventContext(
        game_state=game.state, event=event, investigator_id=inv_id, **kwargs
    )
    game.event_bus.emit(ctx)
    return ctx


def _register(game, impl_cls, instance_id="card_impl"):
    impl = impl_cls(instance_id)
    impl.register(game.event_bus, instance_id)
    return impl


def _play(game, card_id, inv_id="test_investigator", **extra):
    return _emit(game, GameEvent.CARD_PLAYED, inv_id, extra={"card_id": card_id, **extra})


def _add_enemy_at_location(game, instance_id, card_id="test_enemy", location="test_location"):
    game.register_card_data(make_enemy_data(id=card_id))
    enemy = CardInstance(
        instance_id=instance_id, card_id=card_id,
        owner_id="scenario", controller_id="scenario",
    )
    game.state.cards_in_play[instance_id] = enemy
    game.state.locations[location].enemies.append(instance_id)
    return enemy


class TestBlackjack:
    def test_combat_bonus_with_weapon(self, game):
        _register(game, Blackjack, "bj_1")
        ctx = _emit(
            game, GameEvent.SKILL_VALUE_DETERMINED,
            skill_type=Skill.COMBAT, amount=3, source="bj_1",
        )
        assert ctx.amount == 4

    def test_no_bonus_without_weapon_or_wrong_skill(self, game):
        _register(game, Blackjack, "bj_1")
        ctx = _emit(
            game, GameEvent.SKILL_VALUE_DETERMINED,
            skill_type=Skill.COMBAT, amount=3,
        )
        assert ctx.amount == 3
        ctx = _emit(
            game, GameEvent.SKILL_VALUE_DETERMINED,
            skill_type=Skill.INTELLECT, amount=3, source="bj_1",
        )
        assert ctx.amount == 3


class TestTaunt:
    def test_engage_all_enemies(self, game):
        _register(game, Taunt)
        _add_enemy_at_location(game, "e1")
        _add_enemy_at_location(game, "e2")
        inv = game.state.get_investigator("test_investigator")

        ctx = _play(game, "taunt_lv0")
        assert set(ctx.extra["taunt_engaged"]) == {"e1", "e2"}
        assert set(inv.threat_area) == {"e1", "e2"}
        assert game.state.locations["test_location"].enemies == []

    def test_lv2_draws_per_enemy(self, game):
        _register(game, TauntLv2)
        _add_enemy_at_location(game, "e1")
        _add_enemy_at_location(game, "e2")
        inv = game.state.get_investigator("test_investigator")
        inv.deck = ["c1", "c2", "c3"]
        inv.hand = []

        _play(game, "taunt_lv2")
        assert inv.hand == ["c1", "c2"]


class TestTeamwork:
    def test_trade_resources(self, game):
        _register(game, Teamwork)
        inv2_data = make_investigator_data(id="friend")
        game.register_card_data(inv2_data)
        game.add_investigator("friend", inv2_data, starting_location="test_location")

        giver = game.state.get_investigator("test_investigator")
        receiver = game.state.get_investigator("friend")
        giver.resources = 5
        receiver.resources = 1

        assert Teamwork.trade_resources(game.state, "test_investigator", "friend", 3) is True
        assert giver.resources == 2 and receiver.resources == 4
        # 资源不足
        assert Teamwork.trade_resources(game.state, "test_investigator", "friend", 99) is False

    def test_trade_asset(self, game):
        inv2_data = make_investigator_data(id="friend")
        game.register_card_data(inv2_data)
        game.add_investigator("friend", inv2_data, starting_location="test_location")

        giver = game.state.get_investigator("test_investigator")
        asset = CardInstance(
            instance_id="a1", card_id="some_item",
            owner_id="test_investigator", controller_id="test_investigator",
        )
        game.state.cards_in_play["a1"] = asset
        giver.play_area.append("a1")

        # 无卡牌数据时按道具/盟友放行
        assert Teamwork.trade_asset(game.state, "test_investigator", "friend", "a1") is True
        assert "a1" in game.state.get_investigator("friend").play_area


class TestCrackTheCase:
    def test_gain_shroud_resources(self, game):
        _register(game, CrackTheCase)
        inv = game.state.get_investigator("test_investigator")
        inv.resources = 0
        ctx = _play(game, "crack_the_case_lv0")
        assert ctx.extra["crack_the_case_resources"] == game.state.locations["test_location"].shroud
        assert inv.resources == game.state.locations["test_location"].shroud


class TestPreposterousSketchesLv2:
    def test_draw_three(self, game):
        _register(game, PreposterousSketchesLv2)
        inv = game.state.get_investigator("test_investigator")
        inv.deck = ["c1", "c2", "c3", "c4"]
        inv.hand = []
        _play(game, "preposterous_sketches_lv2")
        assert inv.hand == ["c1", "c2", "c3"]


class TestStrangeSolution:
    def test_resolve_success(self, game):
        inv = game.state.get_investigator("test_investigator")
        inst = CardInstance(
            instance_id="sol_1", card_id="strange_solution_lv0",
            owner_id="test_investigator", controller_id="test_investigator",
        )
        game.state.cards_in_play["sol_1"] = inst
        inv.play_area.append("sol_1")
        inv.deck = ["c1", "c2"]
        inv.hand = []

        impl = StrangeSolution("sol_1")
        assert impl.resolve(game.state, "test_investigator", success=True) is True
        assert "sol_1" not in inv.play_area
        assert "strange_solution_lv0" in inv.discard
        assert inv.hand == ["c1", "c2"]
        assert "确认溶液成分" in game.state.scenario.vars["campaign_log"]

    def test_resolve_failure_noop(self, game):
        impl = StrangeSolution("sol_1")
        assert impl.resolve(game.state, "test_investigator", success=False) is False


class TestDoubleOrNothing:
    def test_doubles_difficulty_on_commit(self, game):
        _register(game, DoubleOrNothing)
        ctx = _emit(
            game, GameEvent.SKILL_TEST_COMMIT,
            skill_type=Skill.COMBAT, difficulty=2,
            committed_cards=["double_or_nothing_lv0"],
        )
        assert ctx.extra["double_or_nothing_doubled_difficulty"] == 4
        assert ctx.difficulty == 4

    def test_extra_clue_on_intellect_success(self, game):
        _register(game, DoubleOrNothing)
        inv = game.state.get_investigator("test_investigator")
        inv.clues = 0
        loc = game.state.locations["test_location"]
        assert loc.clues == 3

        ctx = _emit(
            game, GameEvent.SKILL_TEST_SUCCESSFUL,
            skill_type=Skill.INTELLECT, success=True,
            committed_cards=["double_or_nothing_lv0"],
        )
        assert ctx.extra["double_or_nothing"] is True
        assert inv.clues == 1
        assert loc.clues == 2


class TestHiredMuscle:
    def test_combat_bonus_in_play(self, game):
        inv = game.state.get_investigator("test_investigator")
        impl = _register(game, HiredMuscle, "hm_1")
        inst = CardInstance(
            instance_id="hm_1", card_id="hired_muscle_lv1",
            owner_id="test_investigator", controller_id="test_investigator",
        )
        game.state.cards_in_play["hm_1"] = inst
        inv.play_area.append("hm_1")

        ctx = _emit(
            game, GameEvent.SKILL_VALUE_DETERMINED,
            skill_type=Skill.COMBAT, amount=3,
        )
        assert ctx.amount == 4

    def test_upkeep_payment_or_discard(self, game):
        inv = game.state.get_investigator("test_investigator")
        _register(game, HiredMuscle, "hm_1")
        inst = CardInstance(
            instance_id="hm_1", card_id="hired_muscle_lv1",
            owner_id="test_investigator", controller_id="test_investigator",
        )
        game.state.cards_in_play["hm_1"] = inst
        inv.play_area.append("hm_1")

        # 有资源：扣1
        inv.resources = 2
        _emit(game, GameEvent.UPKEEP_PHASE_ENDS)
        assert inv.resources == 1
        assert "hm_1" in inv.play_area

        # 无资源：丢弃雇佣打手
        inv.resources = 0
        _emit(game, GameEvent.UPKEEP_PHASE_ENDS)
        assert "hm_1" not in inv.play_area
        assert "hired_muscle_lv1" in inv.discard


class TestThinkOnYourFeet:
    def test_move_to_first_connected(self, game):
        _register(game, ThinkOnYourFeet)
        loc_b = make_location_data(id="loc_b", connections=["test_location"])
        game.register_card_data(loc_b)
        game.add_location("loc_b", loc_b)
        game.state.locations["test_location"].card_data.connections = ["loc_b"]

        inv = game.state.get_investigator("test_investigator")
        ctx = _play(game, "think_on_your_feet_lv0")
        assert inv.location_id == "loc_b"
        assert ctx.extra["think_on_your_feet_moved_to"] == "loc_b"


class TestBindMonster:
    def test_attach_and_prevent_ready(self, game):
        impl = _register(game, BindMonster)
        enemy = _add_enemy_at_location(game, "e1")

        assert impl.attach_to(game.state, "test_investigator", "e1") is True
        assert enemy.exhausted is True
        assert game.state.scenario.vars["bind_monster_attached"] == "e1"

        # 敌人被就绪 → 重新横置
        enemy.exhausted = False
        ctx = _emit(game, GameEvent.CARD_READIED, target="e1")
        assert enemy.exhausted is True
        assert ctx.extra.get("bind_monster_prevented_ready") is True

    def test_resolve_ready_test_failure_discards(self, game):
        impl = _register(game, BindMonster)
        enemy = _add_enemy_at_location(game, "e1")
        impl.attach_to(game.state, "test_investigator", "e1")

        impl.resolve_ready_test(game.state, success=False)
        assert "bind_monster_attached" not in game.state.scenario.vars
        inv = game.state.get_investigator("test_investigator")
        assert "bind_monster_lv2" in inv.discard
        assert enemy.exhausted is False


class TestKukri:
    def test_combat_bonus(self, game):
        _register(game, Kukri, "k_1")
        ctx = _emit(
            game, GameEvent.SKILL_VALUE_DETERMINED,
            skill_type=Skill.COMBAT, amount=3,
            extra={"weapon_card_id": "kukri_lv0"},
        )
        assert ctx.amount == 4

    def test_bonus_damage_costs_action(self, game):
        inv = game.state.get_investigator("test_investigator")
        inv.actions_remaining = 1
        enemy = _add_enemy_at_location(game, "e1")

        assert Kukri.activate_bonus_damage(game.state, "test_investigator", "e1") is True
        assert enemy.damage == 1
        assert inv.actions_remaining == 0
        # 无额外行动时失败
        assert Kukri.activate_bonus_damage(game.state, "test_investigator", "e1") is False


class TestSearchForTheTruth:
    def test_draw_equal_to_clues_max_five(self, game):
        _register(game, SearchForTheTruth)
        inv = game.state.get_investigator("test_investigator")
        inv.clues = 3
        inv.deck = ["c1", "c2", "c3", "c4", "c5", "c6"]
        inv.hand = []

        ctx = _play(game, "search_for_the_truth_lv0")
        assert ctx.extra["search_for_the_truth_drawn"] == 3
        assert inv.hand == ["c1", "c2", "c3"]

        # 线索超过5时最多抽5
        inv.clues = 7
        inv.deck = ["c1", "c2", "c3", "c4", "c5", "c6"]
        inv.hand = []
        ctx = _play(game, "search_for_the_truth_lv0")
        assert ctx.extra["search_for_the_truth_drawn"] == 5


class TestBaitAndSwitch:
    def test_evade_and_move_enemy(self, game):
        loc_b = make_location_data(id="loc_b", connections=["test_location"])
        game.register_card_data(loc_b)
        game.add_location("loc_b", loc_b)
        game.state.locations["test_location"].card_data.connections = ["loc_b"]

        enemy = _add_enemy_at_location(game, "e1")
        inv = game.state.get_investigator("test_investigator")
        inv.threat_area.append("e1")

        assert BaitAndSwitch.resolve(game.state, "test_investigator", "e1") is True
        assert enemy.exhausted is True
        assert "e1" not in inv.threat_area
        assert "e1" in game.state.locations["loc_b"].enemies
        assert enemy.attached_to == "loc_b"


class TestPeterSylvestreLv2:
    def _setup_peter(self, game):
        inv = game.state.get_investigator("test_investigator")
        impl = _register(game, PeterSylvestreLv2, "p_1")
        inst = CardInstance(
            instance_id="p_1", card_id="peter_sylvestre_lv2",
            owner_id="test_investigator", controller_id="test_investigator",
        )
        game.state.cards_in_play["p_1"] = inst
        inv.play_area.append("p_1")
        return inst

    def test_skill_bonuses(self, game):
        self._setup_peter(game)
        for skill in (Skill.AGILITY, Skill.WILLPOWER):
            ctx = _emit(
                game, GameEvent.SKILL_VALUE_DETERMINED,
                skill_type=skill, amount=2,
            )
            assert ctx.amount == 3
        # 其他技能无加值
        ctx = _emit(
            game, GameEvent.SKILL_VALUE_DETERMINED,
            skill_type=Skill.COMBAT, amount=2,
        )
        assert ctx.amount == 2

    def test_heal_horror_on_turn_end(self, game):
        inst = self._setup_peter(game)
        inst.horror = 2
        _emit(game, GameEvent.INVESTIGATOR_TURN_ENDS)
        assert inst.horror == 1
