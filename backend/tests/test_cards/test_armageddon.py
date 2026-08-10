"""Tests for Armageddon (Level 0 / Level 4). (07117/07226)

花1充能：用意志攻击，+1伤害（lv4 再+2意志）；揭示[curse]时对地点敌人
造成1伤害或在本卡放1充能（简化：自动优先伤害攻击目标，无目标放充能）。
"""

import pytest
from backend.cards.mystic.armageddon_lv0 import Armageddon
from backend.cards.mystic.armageddon_lv4 import ArmageddonLv4
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import ChaosTokenType, GameEvent, Skill
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, ScenarioState,
)
from backend.tests.conftest import (
    make_asset_data, make_enemy_data, make_investigator_data,
)


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    inv_data = make_investigator_data(willpower=5, combat=2)
    state.card_database[inv_data.id] = inv_data
    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1",
    )
    state.investigators["inv1"] = inv

    state.card_database["armageddon_lv0"] = make_asset_data(
        id="armageddon_lv0", name="Armageddon", traits=["spell", "cursed"],
        uses={"charges": 3},
    )
    state.card_database["armageddon_lv4"] = make_asset_data(
        id="armageddon_lv4", name="Armageddon", traits=["spell", "cursed"],
        uses={"charges": 3},
    )
    state.card_database["test_enemy"] = make_enemy_data(health=5)
    return state, bus, inv


def _add_card(state, inv, card_id, instance_id, impl_cls):
    inst = CardInstance(
        instance_id=instance_id, card_id=card_id,
        owner_id="inv1", controller_id="inv1",
    )
    inst.uses = {"charges": 3}
    state.cards_in_play[instance_id] = inst
    inv.play_area.append(instance_id)
    impl = impl_cls(instance_id)
    return inst, impl


def _add_enemy(state, inv, instance_id="enemy_1"):
    enemy = CardInstance(
        instance_id=instance_id, card_id="test_enemy",
        owner_id="scenario", controller_id="scenario",
    )
    state.cards_in_play[instance_id] = enemy
    inv.threat_area.append(instance_id)
    return enemy


def _skill_ctx(state, instance_id, skill=Skill.COMBAT, amount=2):
    return EventContext(
        game_state=state, event=GameEvent.SKILL_VALUE_DETERMINED,
        investigator_id="inv1", skill_type=skill, amount=amount,
        source=instance_id,
    )


class TestArmageddonLv0:
    def test_activate_spends_charge(self, setup):
        state, bus, inv = setup
        inst, impl = _add_card(state, inv, "armageddon_lv0", "inst_arm", Armageddon)
        impl.register(bus, "inst_arm")
        assert impl.activate(state, "inv1") is True
        assert inst.uses["charges"] == 2

    def test_willpower_substitute_no_bonus(self, setup):
        """lv0：意志(5)代替战斗(2)，无额外技能加值。"""
        state, bus, inv = setup
        inst, impl = _add_card(state, inv, "armageddon_lv0", "inst_arm", Armageddon)
        impl.register(bus, "inst_arm")
        impl.activate(state, "inv1")
        ctx = _skill_ctx(state, "inst_arm")
        bus.emit(ctx)
        assert ctx.amount == 5

    def test_bonus_damage_on_success(self, setup):
        state, bus, inv = setup
        inst, impl = _add_card(state, inv, "armageddon_lv0", "inst_arm", Armageddon)
        impl.register(bus, "inst_arm")
        impl.activate(state, "inv1")
        ctx = EventContext(
            game_state=state, event=GameEvent.SKILL_TEST_SUCCESSFUL,
            investigator_id="inv1", skill_type=Skill.COMBAT, success=True,
            source="inst_arm",
        )
        bus.emit(ctx)
        assert ctx.extra["bonus_damage"] == 1

    def test_curse_token_damages_attacked_enemy(self, setup):
        """揭示[curse]：自动对攻击目标造成1伤害。"""
        state, bus, inv = setup
        inst, impl = _add_card(state, inv, "armageddon_lv0", "inst_arm", Armageddon)
        impl.register(bus, "inst_arm")
        enemy = _add_enemy(state, inv)
        impl.activate(state, "inv1")
        bus.emit(EventContext(
            game_state=state, event=GameEvent.FIGHT_ACTION_INITIATED,
            investigator_id="inv1", enemy_id="enemy_1", source="inst_arm",
        ))
        ctx = EventContext(
            game_state=state, event=GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="inv1", chaos_token=ChaosTokenType.CURSE,
            amount=-2, source="inst_arm",
        )
        bus.emit(ctx)
        assert enemy.damage == 1
        assert ctx.extra["armageddon_lv0_curse_damage"] == "enemy_1"

    def test_curse_token_places_charge_without_enemy(self, setup):
        """揭示[curse]但地点无敌人：在本卡放置1充能。"""
        state, bus, inv = setup
        inst, impl = _add_card(state, inv, "armageddon_lv0", "inst_arm", Armageddon)
        impl.register(bus, "inst_arm")
        impl.activate(state, "inv1")
        ctx = EventContext(
            game_state=state, event=GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="inv1", chaos_token=ChaosTokenType.CURSE,
            amount=-2, source="inst_arm",
        )
        bus.emit(ctx)
        assert inst.uses["charges"] == 3  # 2（攻击花费后）+1
        assert ctx.extra["armageddon_lv0_curse_charge"] is True

    def test_no_effect_for_other_weapon(self, setup):
        state, bus, inv = setup
        inst, impl = _add_card(state, inv, "armageddon_lv0", "inst_arm", Armageddon)
        impl.register(bus, "inst_arm")
        impl.activate(state, "inv1")
        ctx = _skill_ctx(state, "other_weapon")
        bus.emit(ctx)
        assert ctx.amount == 2


class TestArmageddonLv4:
    def test_willpower_substitute_plus_2(self, setup):
        """lv4：意志(5)代替战斗(2)并+2意志。"""
        state, bus, inv = setup
        inst, impl = _add_card(state, inv, "armageddon_lv4", "inst_arm4", ArmageddonLv4)
        impl.register(bus, "inst_arm4")
        impl.activate(state, "inv1")
        ctx = _skill_ctx(state, "inst_arm4")
        bus.emit(ctx)
        assert ctx.amount == 7

    def test_curse_damage_per_token(self, setup):
        state, bus, inv = setup
        inst, impl = _add_card(state, inv, "armageddon_lv4", "inst_arm4", ArmageddonLv4)
        impl.register(bus, "inst_arm4")
        enemy = _add_enemy(state, inv)
        impl.activate(state, "inv1")
        bus.emit(EventContext(
            game_state=state, event=GameEvent.FIGHT_ACTION_INITIATED,
            investigator_id="inv1", enemy_id="enemy_1", source="inst_arm4",
        ))
        for _ in range(2):  # lv4：每个[curse]标记各结算一次
            bus.emit(EventContext(
                game_state=state, event=GameEvent.CHAOS_TOKEN_RESOLVED,
                investigator_id="inv1", chaos_token=ChaosTokenType.CURSE,
                amount=-2, source="inst_arm4",
            ))
        assert enemy.damage == 2
