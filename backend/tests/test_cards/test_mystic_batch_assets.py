"""Tests for Flute of the Outer Gods, Ikiaq, Grounded lv3, Mind's Eye,
Four of Cups, Foresight, Open Gate, Parallel Fates, Sacrifice.
"""

import pytest
from backend.cards.mystic.flute_of_the_outer_gods_lv4 import FluteOfTheOuterGods
from backend.cards.mystic.foresight_lv1 import Foresight
from backend.cards.mystic.four_of_cups_lv1 import FourOfCups
from backend.cards.mystic.grounded_lv3 import GroundedLv3
from backend.cards.mystic.ikiaq_lv3 import Ikiaq
from backend.cards.mystic.minds_eye_lv2 import MindsEye
from backend.cards.mystic.open_gate_lv0 import OpenGate
from backend.cards.mystic.parallel_fates_lv2 import ParallelFates
from backend.cards.mystic.sacrifice_lv1 import Sacrifice
from backend.engine.event_bus import EventBus, EventContext
from backend.models.chaos import ChaosBag
from backend.models.enums import ChaosTokenType, GameEvent, Phase, PlayerClass, Skill, SlotType
from backend.models.state import (
    CardData, CardInstance, CardType, GameState, InvestigatorState,
    LocationState, ScenarioState,
)
from backend.tests.conftest import (
    make_asset_data, make_enemy_data, make_investigator_data, make_location_data,
)


def _state(willpower=3, intellect=3, combat=3, agility=3):
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()
    inv_data = make_investigator_data(
        willpower=willpower, intellect=intellect, combat=combat, agility=agility)
    state.card_database[inv_data.id] = inv_data
    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1")
    state.investigators["inv1"] = inv
    for loc_id, conns in (("loc1", ["loc2"]), ("loc2", ["loc1"])):
        ld = make_location_data(id=loc_id, connections=conns)
        state.card_database[loc_id] = ld
        state.locations[loc_id] = LocationState(location_id=loc_id, card_data=ld)
    return state, bus, inv


def _add_asset(state, inv, card_id, instance_id, uses=None, traits=None,
               slots=None, card_class=PlayerClass.MYSTIC):
    state.card_database[card_id] = make_asset_data(
        id=card_id, name=card_id, uses=uses, traits=traits or [],
        slots=slots or [], card_class=card_class)
    inst = CardInstance(
        instance_id=instance_id, card_id=card_id,
        owner_id="inv1", controller_id="inv1")
    if uses:
        inst.uses = dict(uses)
    state.cards_in_play[instance_id] = inst
    inv.play_area.append(instance_id)
    return inst


class TestFluteOfTheOuterGods:
    def _make(self, state, bus, inv):
        inst = _add_asset(state, inv, "flute_of_the_outer_gods_lv4",
                          "inst_flute", slots=[SlotType.HAND])
        bag = ChaosBag()
        bag.add_token(ChaosTokenType.CURSE)
        bag.add_token(ChaosTokenType.CURSE)
        impl = FluteOfTheOuterGods("inst_flute")
        impl.bind_chaos_bag(bag)
        impl.register(bus, "inst_flute")
        bus.emit(EventContext(
            game_state=state, event=GameEvent.CARD_ENTERS_PLAY,
            investigator_id="inv1", target="inst_flute",
            extra={"card_id": "flute_of_the_outer_gods_lv4"}))
        return inst, impl, bag

    def _add_enemy(self, state, loc_id="loc1", iid="enemy_1", traits=None,
                   damage=2):
        ed = make_enemy_data(id="cultist", damage=damage)
        ed = CardData(**{**ed.__dict__, "traits": traits or []})
        state.card_database["cultist"] = ed
        enemy = CardInstance(
            instance_id=iid, card_id="cultist",
            owner_id="scenario", controller_id="scenario")
        state.cards_in_play[iid] = enemy
        state.locations[loc_id].enemies.append(iid)
        return enemy

    def test_enters_play_seals_all_curses(self):
        state, bus, inv = _state()
        inst, impl, bag = self._make(state, bus, inv)
        assert impl._sealed_curses == 2
        assert bag.sealed == [ChaosTokenType.CURSE, ChaosTokenType.CURSE]

    def test_move_enemy_to_connecting_location(self):
        state, bus, inv = _state()
        inst, impl, bag = self._make(state, bus, inv)
        self._add_enemy(state)
        assert impl.activate(state, "inv1", "enemy_1", mode="move") is True
        assert "enemy_1" in state.locations["loc2"].enemies
        assert "enemy_1" not in state.locations["loc1"].enemies
        assert inst.exhausted is True
        assert impl._sealed_curses == 1

    def test_damage_mode_deals_enemy_damage_value(self):
        state, bus, inv = _state()
        inst, impl, bag = self._make(state, bus, inv)
        self._add_enemy(state, damage=2)
        target = self._add_enemy(state, iid="enemy_2")
        assert impl.activate(state, "inv1", "enemy_1", mode="damage",
                             target_enemy_instance_id="enemy_2") is True
        assert target.damage == 2

    def test_elite_rejected(self):
        state, bus, inv = _state()
        inst, impl, bag = self._make(state, bus, inv)
        self._add_enemy(state, traits=["elite"])
        assert impl.activate(state, "inv1", "enemy_1") is False
        assert inst.exhausted is False


class TestIkiaq:
    def _weakness_data(self, state):
        state.card_database["amnesia"] = CardData(
            id="amnesia", name="Amnesia", name_cn="失忆",
            type=CardType.TREACHERY, subtype="basic_weakness")

    def test_skill_bonus_and_weakness_cancel(self):
        state, bus, inv = _state()
        self._weakness_data(state)
        inst = _add_asset(state, inv, "ikiaq_lv3", "inst_ikiaq",
                          slots=[SlotType.ALLY], traits=["ally", "sorcerer"])
        impl = Ikiaq("inst_ikiaq")
        impl.register(bus, "inst_ikiaq")

        ctx = EventContext(
            game_state=state, event=GameEvent.SKILL_VALUE_DETERMINED,
            investigator_id="inv1", skill_type=Skill.WILLPOWER, amount=3)
        bus.emit(ctx)
        assert ctx.amount == 4  # +1意志

        # 抽到基础弱点：取消并压置
        inv.hand.append("amnesia")
        draw_ctx = EventContext(
            game_state=state, event=GameEvent.CARD_DRAWN,
            investigator_id="inv1", extra={"card_id": "amnesia"})
        bus.emit(draw_ctx)
        assert draw_ctx.cancelled is True
        assert "amnesia" not in inv.hand
        assert state.scenario.vars["ikiaq_beneath_inst_ikiaq"] == ["amnesia"]
        assert inst.exhausted is True

        # 压1张弱点后加值归零
        ctx2 = EventContext(
            game_state=state, event=GameEvent.SKILL_VALUE_DETERMINED,
            investigator_id="inv1", skill_type=Skill.INTELLECT, amount=3)
        bus.emit(ctx2)
        assert ctx2.amount == 3

        # 离场：弱点回到拥有者手牌
        bus.emit(EventContext(
            game_state=state, event=GameEvent.CARD_LEAVES_PLAY,
            investigator_id="inv1", target="inst_ikiaq"))
        assert "amnesia" in inv.hand

    def test_non_weakness_draw_untouched(self):
        state, bus, inv = _state()
        inst = _add_asset(state, inv, "ikiaq_lv3", "inst_ikiaq")
        impl = Ikiaq("inst_ikiaq")
        impl.register(bus, "inst_ikiaq")
        ctx = EventContext(
            game_state=state, event=GameEvent.CARD_DRAWN,
            investigator_id="inv1", extra={"card_id": "some_card"})
        bus.emit(ctx)
        assert ctx.cancelled is False
        assert inst.exhausted is False


class TestGroundedLv3:
    def test_passive_spell_boost_and_damage_soak(self):
        state, bus, inv = _state()
        _add_asset(state, inv, "grounded_lv3", "inst_g3",
                   traits=["talent", "composure"])
        # 法术来源（如 Shrivelling 发起的攻击）
        _add_asset(state, inv, "shrivelling_lv0", "inst_shriv",
                   traits=["spell"])
        state.card_database["grounded_lv3"] = make_asset_data(
            id="grounded_lv3", name="Grounded", traits=["talent", "composure"],
            health=2, sanity=2)
        impl = GroundedLv3("inst_g3")
        impl.register(bus, "inst_g3")

        # 法术卡检定 +1
        ctx = EventContext(
            game_state=state, event=GameEvent.SKILL_VALUE_DETERMINED,
            investigator_id="inv1", skill_type=Skill.COMBAT, amount=3,
            source="inst_shriv")
        bus.emit(ctx)
        assert ctx.amount == 4

        # 非法术来源不加
        ctx2 = EventContext(
            game_state=state, event=GameEvent.SKILL_VALUE_DETERMINED,
            investigator_id="inv1", skill_type=Skill.COMBAT, amount=3)
        bus.emit(ctx2)
        assert ctx2.amount == 3

        # 非直接伤害先分配给脚踏实地（体力2，吸收满后被击败离场）
        dmg_ctx = EventContext(
            game_state=state, event=GameEvent.DAMAGE_ASSIGNED,
            investigator_id="inv1", amount=3)
        bus.emit(dmg_ctx)
        assert dmg_ctx.amount == 1  # 吸收2点
        assert dmg_ctx.extra["grounded_lv3_soaked_damage"] == 2
        assert state.get_card_instance("inst_g3") is None  # 吸收满被击败
        assert "grounded_lv3" in inv.discard
        assert "inst_g3" not in inv.play_area

    def test_spell_pump_stacks_with_passive(self):
        state, bus, inv = _state()
        _add_asset(state, inv, "grounded_lv3", "inst_g3",
                   traits=["talent", "composure"])
        _add_asset(state, inv, "shrivelling_lv0", "inst_shriv",
                   traits=["spell"])
        impl = GroundedLv3("inst_g3")
        impl.register(bus, "inst_g3")
        inv.resources = 3
        assert impl.spend(state, "inv1") is True
        ctx = EventContext(
            game_state=state, event=GameEvent.SKILL_VALUE_DETERMINED,
            investigator_id="inv1", skill_type=Skill.COMBAT, amount=3,
            source="inst_shriv")
        bus.emit(ctx)
        assert ctx.amount == 5  # 恒定+1 与泵+1 叠加


class TestMindsEye:
    def test_substitute_when_beneficial(self):
        state, bus, inv = _state(willpower=5, combat=2)
        inst = _add_asset(state, inv, "minds_eye_lv2", "inst_me",
                          uses={"secrets": 3})
        impl = MindsEye("inst_me")
        impl.register(bus, "inst_me")
        ctx = EventContext(
            game_state=state, event=GameEvent.SKILL_VALUE_DETERMINED,
            investigator_id="inv1", skill_type=Skill.COMBAT, amount=2)
        bus.emit(ctx)
        assert ctx.amount == 5
        assert inst.uses["secrets"] == 2

    def test_no_substitute_when_not_beneficial(self):
        state, bus, inv = _state(willpower=2, combat=4)
        inst = _add_asset(state, inv, "minds_eye_lv2", "inst_me",
                          uses={"secrets": 3})
        impl = MindsEye("inst_me")
        impl.register(bus, "inst_me")
        ctx = EventContext(
            game_state=state, event=GameEvent.SKILL_VALUE_DETERMINED,
            investigator_id="inv1", skill_type=Skill.COMBAT, amount=4)
        bus.emit(ctx)
        assert ctx.amount == 4
        assert inst.uses["secrets"] == 3

    def test_discard_copy_adds_secrets(self):
        state, bus, inv = _state()
        inst = _add_asset(state, inv, "minds_eye_lv2", "inst_me",
                          uses={"secrets": 1})
        inv.hand.append("minds_eye_lv2")
        impl = MindsEye("inst_me")
        assert impl.add_secrets(state, "inv1") is True
        assert inst.uses["secrets"] == 3
        assert "minds_eye_lv2" in inv.discard


class TestFourOfCups:
    def test_opening_hand_put_into_play_and_bonus(self):
        state, bus, inv = _state()
        state.scenario.current_phase = Phase.SETUP
        state.card_database["four_of_cups_lv1"] = make_asset_data(
            id="four_of_cups_lv1", name="Four of Cups", traits=["tarot"],
            slots=[SlotType.TAROT])
        inv.hand.append("four_of_cups_lv1")
        impl = FourOfCups("temp")
        impl.register(bus, "temp")

        ctx = EventContext(
            game_state=state, event=GameEvent.CARD_DRAWN,
            investigator_id="inv1", extra={"card_id": "four_of_cups_lv1"})
        bus.emit(ctx)
        assert ctx.extra["four_of_cups_entered_play"] is True
        assert "four_of_cups_lv1" not in inv.hand
        assert len(inv.play_area) == 1

        wp_ctx = EventContext(
            game_state=state, event=GameEvent.SKILL_VALUE_DETERMINED,
            investigator_id="inv1", skill_type=Skill.WILLPOWER, amount=3)
        bus.emit(wp_ctx)
        assert wp_ctx.amount == 4

    def test_not_put_into_play_outside_setup(self):
        state, bus, inv = _state()
        state.scenario.current_phase = Phase.INVESTIGATION
        state.card_database["four_of_cups_lv1"] = make_asset_data(
            id="four_of_cups_lv1", name="Four of Cups", traits=["tarot"])
        inv.hand.append("four_of_cups_lv1")
        impl = FourOfCups("temp")
        impl.register(bus, "temp")
        bus.emit(EventContext(
            game_state=state, event=GameEvent.CARD_DRAWN,
            investigator_id="inv1", extra={"card_id": "four_of_cups_lv1"}))
        assert "four_of_cups_lv1" in inv.hand
        assert inv.play_area == []


class TestForesight:
    def test_cancel_named_draw(self):
        state, bus, inv = _state()
        inv.hand.append("foresight_lv1")
        impl = Foresight("temp")
        impl.register(bus, "temp")
        assert impl.arm(state, "inv1", "dreaded_card") is True

        inv.hand.append("dreaded_card")
        ctx = EventContext(
            game_state=state, event=GameEvent.CARD_DRAWN,
            investigator_id="inv1", extra={"card_id": "dreaded_card"})
        bus.emit(ctx)
        assert ctx.cancelled is True
        assert "dreaded_card" in inv.discard
        assert "dreaded_card" not in inv.hand
        assert "foresight_lv1" in inv.discard  # 已打出
        assert "foresight_lv1" not in inv.hand

    def test_no_trigger_on_other_card(self):
        state, bus, inv = _state()
        inv.hand.append("foresight_lv1")
        impl = Foresight("temp")
        impl.register(bus, "temp")
        impl.arm(state, "inv1", "dreaded_card")
        ctx = EventContext(
            game_state=state, event=GameEvent.CARD_DRAWN,
            investigator_id="inv1", extra={"card_id": "harmless_card"})
        bus.emit(ctx)
        assert ctx.cancelled is False
        assert "foresight_lv1" in inv.hand

    def test_play_mode_puts_asset_into_play_at_minus_2(self):
        state, bus, inv = _state()
        inv.hand.append("foresight_lv1")
        inv.resources = 3
        state.card_database["holy_rosary_lv0"] = make_asset_data(
            id="holy_rosary_lv0", name="Holy Rosary", cost=2,
            slots=[SlotType.ACCESSORY])
        impl = Foresight("temp")
        impl.register(bus, "temp")
        impl.arm(state, "inv1", "holy_rosary_lv0", mode="play")

        inv.hand.append("holy_rosary_lv0")
        ctx = EventContext(
            game_state=state, event=GameEvent.CARD_DRAWN,
            investigator_id="inv1", extra={"card_id": "holy_rosary_lv0"})
        bus.emit(ctx)
        assert ctx.extra["foresight_played"] == "holy_rosary_lv0"
        assert inv.resources == 3  # 费用2 - 2 = 0
        assert "holy_rosary_lv0" not in inv.hand
        assert any(
            state.get_card_instance(iid).card_id == "holy_rosary_lv0"
            for iid in inv.play_area)


class TestOpenGate:
    def test_attach_and_move_via_gate(self):
        state, bus, inv = _state()
        impl = OpenGate("temp1")
        impl.register(bus, "temp1")
        ctx = EventContext(
            game_state=state, event=GameEvent.CARD_PLAYED,
            investigator_id="inv1", extra={"card_id": "open_gate_lv0"})
        bus.emit(ctx)
        assert ctx.extra["open_gate_attached"] == "loc1"

        # 另一扇门前：无法移动
        assert impl.move_via_gate(state, "inv1", "loc2") is False

        # loc2 也叠加开启之门后：视为连接
        inv.location_id = "loc2"
        impl2 = OpenGate("temp2")
        impl2.register(bus, "temp2")
        bus.emit(EventContext(
            game_state=state, event=GameEvent.CARD_PLAYED,
            investigator_id="inv1", extra={"card_id": "open_gate_lv0"}))
        inv.location_id = "loc1"
        assert impl.move_via_gate(state, "inv1", "loc2") is True
        assert inv.location_id == "loc2"

    def test_group_limit_3(self):
        state, bus, inv = _state()
        impl = OpenGate("temp")
        impl.register(bus, "temp")
        for loc_id in ("loc1", "loc2"):
            inv.location_id = loc_id
            bus.emit(EventContext(
                game_state=state, event=GameEvent.CARD_PLAYED,
                investigator_id="inv1", extra={"card_id": "open_gate_lv0"}))
        # 第三个地点 + 第三张门
        ld = make_location_data(id="loc3", connections=["loc1"])
        state.card_database["loc3"] = ld
        state.locations["loc3"] = LocationState(location_id="loc3", card_data=ld)
        inv.location_id = "loc3"
        bus.emit(EventContext(
            game_state=state, event=GameEvent.CARD_PLAYED,
            investigator_id="inv1", extra={"card_id": "open_gate_lv0"}))
        assert len(OpenGate.gated_locations(state)) == 3
        # 第四张失效
        bus.emit(EventContext(
            game_state=state, event=GameEvent.CARD_PLAYED,
            investigator_id="inv1", extra={"card_id": "open_gate_lv0"}))
        assert len(OpenGate.gated_locations(state)) == 3


class TestParallelFates:
    def test_default_keep_order_and_draw(self):
        state, bus, inv = _state()
        inv.deck = ["c1", "c2", "c3", "c4", "c5", "c6", "c7"]
        impl = ParallelFates("temp")
        impl.register(bus, "temp")
        ctx = EventContext(
            game_state=state, event=GameEvent.CARD_PLAYED,
            investigator_id="inv1", extra={"card_id": "parallel_fates_lv2"})
        bus.emit(ctx)
        assert inv.deck == ["c2", "c3", "c4", "c5", "c6", "c7"]  # 抽走c1
        assert inv.hand == ["c1"]

    def test_reorder_top6(self):
        state, bus, inv = _state()
        inv.deck = ["c1", "c2", "c3", "c4", "c5", "c6", "c7"]
        impl = ParallelFates("temp")
        impl.register(bus, "temp")
        ctx = EventContext(
            game_state=state, event=GameEvent.CARD_PLAYED,
            investigator_id="inv1",
            extra={"card_id": "parallel_fates_lv2",
                   "order": [5, 4, 3, 2, 1, 0], "draw": False})
        bus.emit(ctx)
        assert inv.deck == ["c6", "c5", "c4", "c3", "c2", "c1", "c7"]
        assert inv.hand == []

    def test_shuffle_keeps_deck_composition(self):
        state, bus, inv = _state()
        inv.deck = ["c1", "c2", "c3", "c4", "c5", "c6", "c7"]
        impl = ParallelFates("temp")
        impl.register(bus, "temp")
        bus.emit(EventContext(
            game_state=state, event=GameEvent.CARD_PLAYED,
            investigator_id="inv1",
            extra={"card_id": "parallel_fates_lv2",
                   "shuffle": True, "draw": False}))
        assert sorted(inv.deck) == ["c1", "c2", "c3", "c4", "c5", "c6", "c7"]


class TestSacrifice:
    def test_discard_mystic_asset_gain_resources(self):
        state, bus, inv = _state()
        _add_asset(state, inv, "holy_rosary_lv0", "inst_rosary")
        inv.resources = 1
        impl = Sacrifice("temp")
        impl.register(bus, "temp")
        ctx = EventContext(
            game_state=state, event=GameEvent.CARD_PLAYED,
            investigator_id="inv1", extra={"card_id": "sacrifice_lv1"})
        bus.emit(ctx)
        assert ctx.extra["sacrifice_discarded"] == "holy_rosary_lv0"
        assert "inst_rosary" not in inv.play_area
        assert inv.resources == 4  # 默认全取资源

    def test_draw_combination(self):
        state, bus, inv = _state()
        _add_asset(state, inv, "holy_rosary_lv0", "inst_rosary")
        inv.deck = ["c1", "c2", "c3"]
        inv.resources = 0
        impl = Sacrifice("temp")
        impl.register(bus, "temp")
        ctx = EventContext(
            game_state=state, event=GameEvent.CARD_PLAYED,
            investigator_id="inv1",
            extra={"card_id": "sacrifice_lv1", "draw_count": 2})
        bus.emit(ctx)
        assert inv.hand == ["c1", "c2"]
        assert inv.resources == 1

    def test_no_mystic_asset_no_effect(self):
        state, bus, inv = _state()
        inv.resources = 1
        impl = Sacrifice("temp")
        impl.register(bus, "temp")
        ctx = EventContext(
            game_state=state, event=GameEvent.CARD_PLAYED,
            investigator_id="inv1", extra={"card_id": "sacrifice_lv1"})
        bus.emit(ctx)
        assert inv.resources == 1
        assert "sacrifice_discarded" not in ctx.extra
