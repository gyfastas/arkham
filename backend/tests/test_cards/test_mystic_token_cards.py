"""Tests for the bless/curse & token-manipulation mystic cards:
Promise of Power, Prophesy, Occult Theory, Rite of Equilibrium,
Premonition, Protective Incantation, Paradoxical Covenant,
Olive McBride, Recall the Future.
"""

import pytest
from backend.cards.mystic.occult_theory_lv1 import OccultTheory
from backend.cards.mystic.olive_mcbride_lv0 import OliveMcBride
from backend.cards.mystic.paradoxical_covenant_lv2 import ParadoxicalCovenant
from backend.cards.mystic.premonition_lv0 import Premonition
from backend.cards.mystic.promise_of_power_lv0 import PromiseOfPower
from backend.cards.mystic.prophesy_lv0 import Prophesy
from backend.cards.mystic.protective_incantation_lv1 import ProtectiveIncantation
from backend.cards.mystic.recall_the_future_lv2 import RecallTheFuture
from backend.cards.mystic.rite_of_equilibrium_lv5 import RiteOfEquilibrium
from backend.engine.event_bus import EventBus, EventContext
from backend.models.chaos import ChaosBag
from backend.models.enums import ChaosTokenType, GameEvent, Skill
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, LocationState, ScenarioState,
)
from backend.tests.conftest import make_asset_data, make_investigator_data, make_location_data


def _state(willpower=3, intellect=3):
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()
    inv_data = make_investigator_data(willpower=willpower, intellect=intellect)
    state.card_database[inv_data.id] = inv_data
    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1")
    state.investigators["inv1"] = inv
    ld = make_location_data(id="loc1")
    state.card_database["loc1"] = ld
    state.locations["loc1"] = LocationState(location_id="loc1", card_data=ld)
    return state, bus, inv


def _add_asset(state, inv, card_id, instance_id, uses=None, traits=None):
    state.card_database[card_id] = make_asset_data(
        id=card_id, name=card_id, uses=uses, traits=traits or [])
    inst = CardInstance(
        instance_id=instance_id, card_id=card_id,
        owner_id="inv1", controller_id="inv1")
    if uses:
        inst.uses = dict(uses)
    state.cards_in_play[instance_id] = inst
    inv.play_area.append(instance_id)
    return inst


class TestPromiseOfPower:
    def test_commit_adds_curse(self):
        state, bus, inv = _state()
        bag = ChaosBag()
        impl = PromiseOfPower("temp")
        impl.bind_chaos_bag(bag)
        impl.register(bus, "temp")
        ctx = EventContext(
            game_state=state, event=GameEvent.SKILL_TEST_COMMIT,
            investigator_id="inv1", skill_type=Skill.WILLPOWER,
            committed_cards=["promise_of_power_lv0"], amount=4)
        bus.emit(ctx)
        assert bag.tokens.count(ChaosTokenType.CURSE) == 1
        assert ctx.extra["promise_of_power_curse_added"] is True

    def test_full_curses_takes_horror(self):
        state, bus, inv = _state()
        bag = ChaosBag()
        for _ in range(10):
            bag.add_token(ChaosTokenType.CURSE)
        impl = PromiseOfPower("temp")
        impl.bind_chaos_bag(bag)
        impl.register(bus, "temp")
        ctx = EventContext(
            game_state=state, event=GameEvent.SKILL_TEST_COMMIT,
            investigator_id="inv1", skill_type=Skill.WILLPOWER,
            committed_cards=["promise_of_power_lv0"], amount=4)
        bus.emit(ctx)
        assert inv.horror == 2
        assert ctx.extra["promise_of_power_horror"] == 2


class TestProphesy:
    @pytest.mark.parametrize("doom,bonus", [(0, 0), (3, 1), (5, 1), (6, 2)])
    def test_doom_scaling(self, doom, bonus):
        state, bus, inv = _state()
        state.scenario.doom_on_agenda = doom
        impl = Prophesy("temp")
        impl.register(bus, "temp")
        ctx = EventContext(
            game_state=state, event=GameEvent.SKILL_TEST_COMMIT,
            investigator_id="inv1", skill_type=Skill.COMBAT,
            committed_cards=["prophesy_lv0"], amount=1)
        bus.emit(ctx)
        assert ctx.amount == 1 + bonus


class TestOccultTheory:
    def test_intellect_test_gains_willpower_icons(self):
        state, bus, inv = _state(willpower=4, intellect=2)
        impl = OccultTheory("temp")
        impl.register(bus, "temp")
        ctx = EventContext(
            game_state=state, event=GameEvent.SKILL_TEST_COMMIT,
            investigator_id="inv1", skill_type=Skill.INTELLECT,
            committed_cards=["occult_theory_lv1"], amount=0)
        bus.emit(ctx)
        assert ctx.amount == 4  # 等于意志值

    def test_willpower_test_gains_intellect_icons(self):
        state, bus, inv = _state(willpower=4, intellect=2)
        impl = OccultTheory("temp")
        impl.register(bus, "temp")
        ctx = EventContext(
            game_state=state, event=GameEvent.SKILL_TEST_COMMIT,
            investigator_id="inv1", skill_type=Skill.WILLPOWER,
            committed_cards=["occult_theory_lv1"], amount=0)
        bus.emit(ctx)
        assert ctx.amount == 2  # 等于智力值

    def test_other_skill_no_icons(self):
        state, bus, inv = _state(willpower=4, intellect=2)
        impl = OccultTheory("temp")
        impl.register(bus, "temp")
        ctx = EventContext(
            game_state=state, event=GameEvent.SKILL_TEST_COMMIT,
            investigator_id="inv1", skill_type=Skill.COMBAT,
            committed_cards=["occult_theory_lv1"], amount=0)
        bus.emit(ctx)
        assert ctx.amount == 0


class TestRiteOfEquilibrium:
    def test_exchange_adds_pairs(self):
        state, bus, inv = _state()
        bag = ChaosBag()
        impl = RiteOfEquilibrium("temp")
        impl.bind_chaos_bag(bag)
        impl.register(bus, "temp")
        ctx = EventContext(
            game_state=state, event=GameEvent.CARD_PLAYED,
            investigator_id="inv1",
            extra={"card_id": "rite_of_equilibrium_lv5",
                   "mode": "exchange", "x": 2})
        bus.emit(ctx)
        assert bag.tokens.count(ChaosTokenType.CURSE) == 2
        assert bag.tokens.count(ChaosTokenType.BLESS) == 2
        assert ctx.extra["rite_of_equilibrium_added"] == 2

    def test_remove_and_heal(self):
        state, bus, inv = _state()
        inv.horror = 3
        bag = ChaosBag()
        bag.add_token(ChaosTokenType.CURSE)
        bag.add_token(ChaosTokenType.BLESS)
        impl = RiteOfEquilibrium("temp")
        impl.bind_chaos_bag(bag)
        impl.register(bus, "temp")
        ctx = EventContext(
            game_state=state, event=GameEvent.CARD_PLAYED,
            investigator_id="inv1",
            extra={"card_id": "rite_of_equilibrium_lv5",
                   "mode": "heal", "x": 1})
        bus.emit(ctx)
        assert ChaosTokenType.CURSE not in bag.tokens
        assert ChaosTokenType.BLESS not in bag.tokens
        assert inv.horror == 2
        assert ctx.extra["rite_of_equilibrium_healed"] == 1


class TestPremonition:
    def test_seal_then_resolve_sealed_token(self):
        state, bus, inv = _state()
        bag = ChaosBag(tokens=[ChaosTokenType.MINUS_2])
        impl = Premonition("temp")
        impl.bind_chaos_bag(bag)
        impl.register(bus, "temp")

        play_ctx = EventContext(
            game_state=state, event=GameEvent.CARD_PLAYED,
            investigator_id="inv1", extra={"card_id": "premonition_lv0"})
        bus.emit(play_ctx)
        assert play_ctx.extra["premonition_sealed"] == "-2"
        assert bag.sealed == [ChaosTokenType.MINUS_2]
        assert bag.tokens == []
        inst_id = impl._play_instance_id
        assert inst_id in inv.play_area

        # 下一次揭示：原抽到的标记被替换为封印的 -2
        ctx = EventContext(
            game_state=state, event=GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="inv1", chaos_token=ChaosTokenType.PLUS_1, amount=1)
        bus.emit(ctx)
        assert ctx.chaos_token == ChaosTokenType.MINUS_2
        assert ctx.amount == -2
        # 预感被弃掉，封印标记释放回袋
        assert inst_id not in inv.play_area
        assert "premonition_lv0" in inv.discard
        assert bag.tokens == [ChaosTokenType.MINUS_2]
        assert bag.sealed == []


class TestProtectiveIncantation:
    def test_seal_worst_token_and_pay_upkeep(self):
        state, bus, inv = _state()
        _add_asset(state, inv, "protective_incantation_lv1", "inst_pi")
        bag = ChaosBag()  # 标准袋最差非auto_fail为 -3
        impl = ProtectiveIncantation("inst_pi")
        impl.bind_chaos_bag(bag)
        impl.register(bus, "inst_pi")

        enter_ctx = EventContext(
            game_state=state, event=GameEvent.CARD_ENTERS_PLAY,
            investigator_id="inv1", target="inst_pi",
            extra={"card_id": "protective_incantation_lv1"})
        bus.emit(enter_ctx)
        assert enter_ctx.extra["protective_incantation_sealed"] == "-3"
        assert bag.sealed == [ChaosTokenType.MINUS_3]

        # 回合结束：有资源自动付1
        inv.resources = 2
        end_ctx = EventContext(
            game_state=state, event=GameEvent.INVESTIGATOR_TURN_ENDS,
            investigator_id="inv1")
        bus.emit(end_ctx)
        assert inv.resources == 1
        assert "inst_pi" in inv.play_area

    def test_no_resources_discards_and_releases(self):
        state, bus, inv = _state()
        _add_asset(state, inv, "protective_incantation_lv1", "inst_pi")
        bag = ChaosBag()
        impl = ProtectiveIncantation("inst_pi")
        impl.bind_chaos_bag(bag)
        impl.register(bus, "inst_pi")
        bus.emit(EventContext(
            game_state=state, event=GameEvent.CARD_ENTERS_PLAY,
            investigator_id="inv1", target="inst_pi",
            extra={"card_id": "protective_incantation_lv1"}))
        sealed_before = list(bag.sealed)

        inv.resources = 0
        ctx = EventContext(
            game_state=state, event=GameEvent.INVESTIGATOR_TURN_ENDS,
            investigator_id="inv1")
        bus.emit(ctx)
        assert ctx.extra["protective_incantation_discarded"] is True
        assert "inst_pi" not in inv.play_area
        assert "protective_incantation_lv1" in inv.discard
        assert bag.sealed == []  # 封印标记已释放
        assert ChaosTokenType.MINUS_3 in bag.tokens or not sealed_before


class TestParadoxicalCovenant:
    def test_bless_and_curse_auto_success(self):
        state, bus, inv = _state()
        inst = _add_asset(state, inv, "paradoxical_covenant_lv2", "inst_pc")
        bag = ChaosBag(tokens=[
            ChaosTokenType.BLESS, ChaosTokenType.CURSE,
            ChaosTokenType.ZERO,
        ])
        impl = ParadoxicalCovenant("inst_pc")
        impl.bind_chaos_bag(bag)
        impl.register(bus, "inst_pc")

        bus.emit(EventContext(
            game_state=state, event=GameEvent.SKILL_TEST_BEGINS,
            investigator_id="inv1", skill_type=Skill.WILLPOWER))
        bus.emit(EventContext(
            game_state=state, event=GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="inv1", chaos_token=ChaosTokenType.BLESS, amount=2))
        ctx = EventContext(
            game_state=state, event=GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="inv1", chaos_token=ChaosTokenType.CURSE, amount=-2)
        bus.emit(ctx)
        assert inst.exhausted is True
        assert ctx.extra["paradoxical_covenant_triggered"] is True

        fail_ctx = EventContext(
            game_state=state, event=GameEvent.SKILL_TEST_FAILED,
            investigator_id="inv1", success=False)
        bus.emit(fail_ctx)
        assert fail_ctx.success is True

        bus.emit(EventContext(
            game_state=state, event=GameEvent.SKILL_TEST_ENDS,
            investigator_id="inv1"))
        assert ChaosTokenType.BLESS not in bag.tokens
        assert ChaosTokenType.CURSE not in bag.tokens
        assert bag.tokens == [ChaosTokenType.ZERO]

    def test_single_kind_does_not_trigger(self):
        state, bus, inv = _state()
        inst = _add_asset(state, inv, "paradoxical_covenant_lv2", "inst_pc")
        impl = ParadoxicalCovenant("inst_pc")
        impl.bind_chaos_bag(ChaosBag())
        impl.register(bus, "inst_pc")
        bus.emit(EventContext(
            game_state=state, event=GameEvent.SKILL_TEST_BEGINS,
            investigator_id="inv1"))
        bus.emit(EventContext(
            game_state=state, event=GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="inv1", chaos_token=ChaosTokenType.BLESS, amount=2))
        assert inst.exhausted is False


class TestOliveMcBride:
    def test_reveal_three_keep_two(self):
        """原标记 0；袋中仅 -3（draw 不移除标记，补抽必为 -3）：
        三枚为 0/-3/-3，忽略最差的1枚，结算 0 与 -3。"""
        state, bus, inv = _state()
        inst = _add_asset(state, inv, "olive_mcbride_lv0", "inst_om")
        bag = ChaosBag(tokens=[ChaosTokenType.MINUS_3])
        impl = OliveMcBride("inst_om")
        impl.bind_chaos_bag(bag)
        impl.register(bus, "inst_om")

        ctx = EventContext(
            game_state=state, event=GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="inv1", chaos_token=ChaosTokenType.ZERO, amount=0)
        bus.emit(ctx)
        assert inst.exhausted is True
        assert sorted(ctx.extra["olive_mcbride_tokens"]) == ["-3", "-3", "0"]
        assert ctx.extra["olive_mcbride_kept"] == ["0", "-3"]
        assert ctx.amount == -3

    def test_reveal_three_all_good(self):
        """袋中仅 +1：三枚为 0/+1/+1，全部保留两枚较优者，修正+2。"""
        state, bus, inv = _state()
        inst = _add_asset(state, inv, "olive_mcbride_lv0", "inst_om")
        bag = ChaosBag(tokens=[ChaosTokenType.PLUS_1])
        impl = OliveMcBride("inst_om")
        impl.bind_chaos_bag(bag)
        impl.register(bus, "inst_om")

        ctx = EventContext(
            game_state=state, event=GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="inv1", chaos_token=ChaosTokenType.ZERO, amount=0)
        bus.emit(ctx)
        assert ctx.extra["olive_mcbride_kept"] == ["+1", "+1"]
        assert ctx.amount == 2
        assert ctx.extra["cancel_auto_fail"] is True

    def test_exhausted_olive_does_not_trigger(self):
        state, bus, inv = _state()
        inst = _add_asset(state, inv, "olive_mcbride_lv0", "inst_om")
        inst.exhausted = True
        impl = OliveMcBride("inst_om")
        impl.bind_chaos_bag(ChaosBag())
        impl.register(bus, "inst_om")
        ctx = EventContext(
            game_state=state, event=GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="inv1", chaos_token=ChaosTokenType.ZERO, amount=0)
        bus.emit(ctx)
        assert "olive_mcbride_tokens" not in ctx.extra
        assert ctx.amount == 0


class TestRecallTheFuture:
    def test_named_token_hit_boosts(self):
        state, bus, inv = _state()
        inst = _add_asset(state, inv, "recall_the_future_lv2", "inst_rtf")
        impl = RecallTheFuture("inst_rtf")
        impl.register(bus, "inst_rtf")

        assert impl.arm(state, "inv1", ChaosTokenType.SKULL) is True
        bus.emit(EventContext(
            game_state=state, event=GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="inv1", chaos_token=ChaosTokenType.SKULL, amount=-1))
        assert inst.exhausted is True

        ctx = EventContext(
            game_state=state, event=GameEvent.SKILL_VALUE_DETERMINED,
            investigator_id="inv1", skill_type=Skill.INTELLECT, amount=3)
        bus.emit(ctx)
        assert ctx.amount == 5

    def test_miss_no_boost(self):
        state, bus, inv = _state()
        inst = _add_asset(state, inv, "recall_the_future_lv2", "inst_rtf")
        impl = RecallTheFuture("inst_rtf")
        impl.register(bus, "inst_rtf")
        impl.arm(state, "inv1", ChaosTokenType.SKULL)
        bus.emit(EventContext(
            game_state=state, event=GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="inv1", chaos_token=ChaosTokenType.ZERO, amount=0))
        assert inst.exhausted is False
        ctx = EventContext(
            game_state=state, event=GameEvent.SKILL_VALUE_DETERMINED,
            investigator_id="inv1", skill_type=Skill.INTELLECT, amount=3)
        bus.emit(ctx)
        assert ctx.amount == 3
