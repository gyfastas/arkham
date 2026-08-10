"""Tests for Spectral Razor (lv0), Sword Cane (lv0), Summoned Hound (lv1)."""

import pytest

from backend.cards.mystic.spectral_razor_lv0 import SpectralRazor
from backend.cards.mystic.summoned_hound_lv1 import SummonedHound
from backend.cards.mystic.sword_cane_lv0 import SwordCane
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent, Skill
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, LocationState, ScenarioState,
)
from backend.tests.conftest import (
    make_asset_data, make_enemy_data, make_event_data,
    make_investigator_data, make_location_data,
)


def _base_state(willpower=4, combat=3, agility=2):
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()
    inv_data = make_investigator_data(
        willpower=willpower, combat=combat, agility=agility)
    state.card_database[inv_data.id] = inv_data
    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1")
    state.investigators["inv1"] = inv
    loc = make_location_data(id="loc1")
    state.card_database["loc1"] = loc
    state.locations["loc1"] = LocationState(location_id="loc1", card_data=loc)
    return state, bus, inv


def _add_enemy(state, inv, elite=False, engaged=False):
    enemy_data = make_enemy_data(fight=3, health=5, evade=3,
                                 keywords=["elite"] if elite else [])
    state.card_database["test_enemy"] = enemy_data
    enemy = CardInstance(
        instance_id="enemy1", card_id="test_enemy",
        owner_id="scenario", controller_id="scenario",
    )
    state.cards_in_play["enemy1"] = enemy
    if engaged:
        inv.threat_area.append("enemy1")
    else:
        state.locations["loc1"].enemies.append("enemy1")
    return enemy


def _emit(bus, state, event, **kwargs):
    ctx = EventContext(game_state=state, event=event, investigator_id="inv1", **kwargs)
    bus.emit(ctx)
    return ctx


class TestSpectralRazor:
    CID = "spectral_razor_lv0"

    def _play(self, state, bus, inv):
        state.card_database[self.CID] = make_event_data(id=self.CID, cost=2)
        impl = SpectralRazor("evt1")
        impl.register(bus, "evt1")
        _emit(bus, state, GameEvent.CARD_PLAYED, extra={"card_id": self.CID})
        return impl

    def test_engage_and_add_willpower(self):
        state, bus, inv = _base_state()
        _add_enemy(state, inv, engaged=False)
        self._play(state, bus, inv)
        ctx = _emit(bus, state, GameEvent.FIGHT_ACTION_INITIATED,
                    enemy_id="enemy1")
        # 攻击前自动交战
        assert "enemy1" in inv.threat_area
        assert "enemy1" not in state.locations["loc1"].enemies
        assert ctx.extra["spectral_razor_engaged"] is True
        # 技能值加入意志（3战斗+4意志）
        ctx = _emit(bus, state, GameEvent.SKILL_VALUE_DETERMINED,
                    skill_type=Skill.COMBAT, amount=3)
        assert ctx.amount == 7

    def test_bonus_damage_non_elite(self):
        state, bus, inv = _base_state()
        _add_enemy(state, inv, engaged=True)
        self._play(state, bus, inv)
        _emit(bus, state, GameEvent.FIGHT_ACTION_INITIATED, enemy_id="enemy1")
        ctx = _emit(bus, state, GameEvent.SKILL_TEST_SUCCESSFUL,
                    skill_type=Skill.COMBAT, success=True)
        assert ctx.extra["bonus_damage"] == 2

    def test_bonus_damage_elite(self):
        state, bus, inv = _base_state()
        _add_enemy(state, inv, elite=True, engaged=True)
        self._play(state, bus, inv)
        _emit(bus, state, GameEvent.FIGHT_ACTION_INITIATED, enemy_id="enemy1")
        ctx = _emit(bus, state, GameEvent.SKILL_TEST_SUCCESSFUL,
                    skill_type=Skill.COMBAT, success=True)
        assert ctx.extra["bonus_damage"] == 1


class TestSwordCane:
    CID = "sword_cane_lv0"

    def _setup(self):
        state, bus, inv = _base_state(willpower=5, combat=2, agility=2)
        state.card_database[self.CID] = make_asset_data(id=self.CID)
        inst = CardInstance(
            instance_id="inst1", card_id=self.CID,
            owner_id="inv1", controller_id="inv1",
        )
        state.cards_in_play["inst1"] = inst
        inv.play_area.append("inst1")
        impl = SwordCane("inst1")
        impl.register(bus, "inst1")
        return state, bus, inv, inst, impl

    def test_play_provokes_no_aoo(self):
        state, bus, inv, inst, impl = self._setup()
        _emit(bus, state, GameEvent.CARD_ENTERS_PLAY, target="inst1",
              extra={"card_id": self.CID})
        ctx = _emit(bus, state, GameEvent.ATTACK_OF_OPPORTUNITY,
                    enemy_id="enemy1")
        assert ctx.cancelled is True
        # 打出行动结束后，后续行动的趁乱攻击不再豁免
        _emit(bus, state, GameEvent.ACTION_PERFORMED)
        ctx = _emit(bus, state, GameEvent.ATTACK_OF_OPPORTUNITY,
                    enemy_id="enemy1")
        assert ctx.cancelled is False

    def test_free_use_after_enters_play(self):
        """入场反应：下一次战斗/躲避可用意志代替（不消耗）。"""
        state, bus, inv, inst, impl = self._setup()
        _emit(bus, state, GameEvent.CARD_ENTERS_PLAY, target="inst1",
              extra={"card_id": self.CID})
        ctx = _emit(bus, state, GameEvent.SKILL_VALUE_DETERMINED,
                    skill_type=Skill.AGILITY, amount=2)
        assert ctx.amount == 5
        assert inst.exhausted is False
        _emit(bus, state, GameEvent.SKILL_TEST_ENDS, success=True)
        # 免费启动已消耗
        ctx = _emit(bus, state, GameEvent.SKILL_VALUE_DETERMINED,
                    skill_type=Skill.AGILITY, amount=2)
        assert ctx.amount == 2

    def test_activate_fight_exhausts_and_substitutes(self):
        state, bus, inv, inst, impl = self._setup()
        assert impl.activate_fight(state, "inv1", "enemy1") is True
        assert inst.exhausted is True
        ctx = _emit(bus, state, GameEvent.SKILL_VALUE_DETERMINED,
                    skill_type=Skill.COMBAT, amount=2)
        assert ctx.amount == 5
        # 横置后不能再次启动
        assert impl.activate_evade(state, "inv1", "enemy1") is False


class TestSummonedHound:
    CID = "summoned_hound_lv1"

    def _setup(self):
        state, bus, inv = _base_state(combat=2)
        state.card_database[self.CID] = make_asset_data(
            id=self.CID, health=3, traits=["ally", "summon"])
        inst = CardInstance(
            instance_id="inst1", card_id=self.CID,
            owner_id="inv1", controller_id="inv1",
        )
        state.cards_in_play["inst1"] = inst
        inv.play_area.append("inst1")
        impl = SummonedHound("inst1")
        impl.register(bus, "inst1")
        return state, bus, inv, inst, impl

    def test_bonded_beast_shuffled_into_deck(self):
        state, bus, inv, inst, impl = self._setup()
        _emit(bus, state, GameEvent.CARD_ENTERS_PLAY, target="inst1",
              extra={"card_id": self.CID})
        assert "unbound_beast_lv0" in inv.deck

    def test_fight_with_base_combat_5(self):
        """基础战斗5：原战斗2 → +3（投入图标1正常叠加）。"""
        state, bus, inv, inst, impl = self._setup()
        assert impl.activate_fight(state, "inv1", "enemy1") is True
        assert inst.exhausted is True
        ctx = _emit(bus, state, GameEvent.SKILL_VALUE_DETERMINED,
                    skill_type=Skill.COMBAT, amount=3, source="inst1")
        assert ctx.amount == 6  # 5基础 + 1投入图标

    def test_investigate_with_base_intellect_5(self):
        """基础智力5：原智力3 + 1投入图标 → 6。"""
        state, bus, inv, inst, impl = self._setup()
        assert impl.activate_investigate(state, "inv1") is True
        ctx = _emit(bus, state, GameEvent.SKILL_VALUE_DETERMINED,
                    skill_type=Skill.INTELLECT, amount=4)
        assert ctx.amount == 6
