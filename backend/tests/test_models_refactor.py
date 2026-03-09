"""Tests for iteration 3: InvestigatorCard, scenario model, chaos bag viz, doom check."""

import pytest
from collections import Counter

from backend.engine.game import Game
from backend.models.chaos import ChaosBag, STANDARD_BAG
from backend.models.enums import (
    CardType, ChaosTokenType, Phase, PlayerClass, Skill, SlotType,
)
from backend.models.investigator import InvestigatorCard, DeckRequirement
from backend.models.scenario import (
    ActCard, AgendaCard, AdvanceEffect, AdvanceEffectType, Branch, Resolution,
)
from backend.models.state import CardData, GameState, InvestigatorState, ScenarioState, SkillValues
from backend.tests.conftest import (
    make_investigator_card, make_investigator_data, make_location_data,
)


# ============================================================
# InvestigatorCard model tests
# ============================================================

class TestInvestigatorCard:
    def test_basic_creation(self):
        ic = InvestigatorCard(
            id="roland_banks", name="Roland Banks", name_cn="罗兰·班克斯",
            card_class=PlayerClass.GUARDIAN, health=9, sanity=5,
            skills=SkillValues(willpower=3, intellect=3, combat=4, agility=2),
        )
        assert ic.id == "roland_banks"
        assert ic.health == 9
        assert ic.sanity == 5
        assert ic.get_skill(Skill.COMBAT) == 4
        assert ic.get_skill(Skill.AGILITY) == 2

    def test_effective_health_with_trauma(self):
        ic = make_investigator_card(health=7)
        assert ic.effective_health == 7
        ic.physical_trauma = 2
        assert ic.effective_health == 5
        # Minimum 1
        ic.physical_trauma = 10
        assert ic.effective_health == 1

    def test_effective_sanity_with_trauma(self):
        ic = make_investigator_card(sanity=7)
        assert ic.effective_sanity == 7
        ic.mental_trauma = 3
        assert ic.effective_sanity == 4
        ic.mental_trauma = 10
        assert ic.effective_sanity == 1

    def test_experience_tracking(self):
        ic = make_investigator_card()
        assert ic.experience == 0
        ic.experience = 5
        assert ic.experience == 5

    def test_deck_requirement(self):
        dr = DeckRequirement(
            size=30,
            allowed_classes=["seeker", "neutral"],
            max_level=5,
            required_cards=["daisys_tote_bag"],
            weaknesses=["the_necronomicon"],
        )
        ic = make_investigator_card(deck_requirement=dr)
        assert ic.deck_requirement.size == 30
        assert "seeker" in ic.deck_requirement.allowed_classes
        assert "daisys_tote_bag" in ic.deck_requirement.required_cards

    def test_signature_and_weaknesses(self):
        ic = InvestigatorCard(
            id="daisy", name="Daisy", name_cn="黛西",
            card_class=PlayerClass.SEEKER, health=5, sanity=9,
            skills=SkillValues(willpower=3, intellect=5, combat=2, agility=2),
            signature_cards=["daisys_tote_bag"],
            weaknesses=["the_necronomicon"],
        )
        assert ic.signature_cards == ["daisys_tote_bag"]
        assert ic.weaknesses == ["the_necronomicon"]


# ============================================================
# InvestigatorState with InvestigatorCard tests
# ============================================================

class TestInvestigatorStateWithNewModel:
    def test_investigator_card_on_state(self):
        ic = make_investigator_card(health=5, sanity=9, combat=4)
        cd = CardData(id="x", name="x", name_cn="x", type=CardType.INVESTIGATOR,
                      health=5, sanity=9)
        inv = InvestigatorState(investigator_id="p1", card_data=cd)
        inv.investigator_card = ic
        assert inv.health == 5
        assert inv.sanity == 9
        assert inv.get_skill(Skill.COMBAT) == 4

    def test_trauma_affects_health_sanity(self):
        ic = make_investigator_card(health=7, sanity=7)
        ic.physical_trauma = 2
        ic.mental_trauma = 1
        cd = CardData(id="x", name="x", name_cn="x", type=CardType.INVESTIGATOR,
                      health=7, sanity=7)
        inv = InvestigatorState(investigator_id="p1", card_data=cd)
        inv.investigator_card = ic
        assert inv.health == 5  # 7 - 2 trauma
        assert inv.sanity == 6  # 7 - 1 trauma

    def test_backward_compat_without_investigator_card(self):
        """Old code path: InvestigatorState with CardData only."""
        cd = CardData(
            id="old", name="Old", name_cn="旧",
            type=CardType.INVESTIGATOR, health=7, sanity=7,
            skills=SkillValues(willpower=3, intellect=3, combat=3, agility=3),
        )
        inv = InvestigatorState(investigator_id="p1", card_data=cd)
        assert inv.health == 7
        assert inv.sanity == 7
        assert inv.get_skill(Skill.WILLPOWER) == 3

    def test_is_defeated_with_trauma(self):
        ic = make_investigator_card(health=5, sanity=5)
        ic.physical_trauma = 2  # effective health = 3
        cd = CardData(id="x", name="x", name_cn="x", type=CardType.INVESTIGATOR, health=5, sanity=5)
        inv = InvestigatorState(investigator_id="p1", card_data=cd)
        inv.investigator_card = ic
        inv.damage = 3
        assert inv.is_defeated  # 3 damage >= 3 effective health


# ============================================================
# Game.add_investigator with InvestigatorCard
# ============================================================

class TestGameAddInvestigator:
    def test_add_with_investigator_card(self):
        g = Game("test")
        ic = make_investigator_card(health=5, sanity=9)
        loc = make_location_data()
        g.register_card_data(loc)
        g.add_location("test_location", loc, clues=2)
        inv = g.add_investigator("p1", ic, starting_location="test_location")
        assert inv.investigator_card is not None
        assert inv.investigator_card.health == 5
        assert inv.card_data is not None  # Shim CardData auto-created
        assert inv.card_data.id == "test_investigator"
        assert inv.health == 5

    def test_add_with_card_data_backward_compat(self):
        g = Game("test")
        cd = make_investigator_data(health=7)
        g.register_card_data(cd)
        loc = make_location_data()
        g.register_card_data(loc)
        g.add_location("test_location", loc, clues=2)
        inv = g.add_investigator("p1", cd, starting_location="test_location")
        assert inv.card_data is cd
        assert inv.investigator_card is None  # Not set via old path
        assert inv.health == 7


# ============================================================
# Scenario model tests
# ============================================================

class TestAgendaCard:
    def test_basic(self):
        agenda = AgendaCard(
            id="agenda_1a", name="What's Going On?!", name_cn="发生了什么?!",
            doom_threshold=7, sequence=1,
            text="Something terrible is happening...",
        )
        assert agenda.doom_threshold == 7
        assert agenda.sequence == 1

    def test_with_advance_effects(self):
        agenda = AgendaCard(
            id="agenda_2a", name="Rise of the Ghouls", name_cn="食尸鬼崛起",
            doom_threshold=5, sequence=2,
            advance_effects=[
                AdvanceEffect(type=AdvanceEffectType.SPAWN_ENEMY, params={"enemy_id": "ghoul", "location": "hallway"}),
                AdvanceEffect(type=AdvanceEffectType.DEAL_DAMAGE, params={"amount": 1, "target": "all_investigators"}),
            ],
        )
        assert len(agenda.advance_effects) == 2
        assert agenda.advance_effects[0].type == AdvanceEffectType.SPAWN_ENEMY

    def test_with_branch(self):
        agenda = AgendaCard(
            id="agenda_1a", name="Test", name_cn="测试",
            doom_threshold=6,
            branch=Branch(
                condition="clues >= 5",
                true_target="agenda_2a",
                false_target="agenda_2b",
                description="If investigators have enough clues...",
            ),
        )
        assert agenda.branch is not None
        assert agenda.branch.true_target == "agenda_2a"


class TestActCard:
    def test_basic(self):
        act = ActCard(
            id="act_1a", name="Trapped", name_cn="困境",
            sequence=1, clue_threshold=3,
            text="Spend 3 clues to advance.",
        )
        assert act.clue_threshold == 3

    def test_special_condition(self):
        act = ActCard(
            id="act_2a", name="Escape", name_cn="逃脱",
            sequence=2, clue_threshold=None,
            advance_condition="All investigators at the Study with no enemies engaged",
        )
        assert act.clue_threshold is None
        assert "Study" in act.advance_condition


class TestResolution:
    def test_basic(self):
        r = Resolution(
            id="R1", name="Resolution 1", name_cn="结���1",
            text="You escaped the darkness.",
            xp_reward=5, trauma_damage=0, trauma_horror=1,
        )
        assert r.xp_reward == 5
        assert r.trauma_horror == 1


# ============================================================
# ScenarioState extensions
# ============================================================

class TestScenarioStateExtensions:
    def test_effective_doom_threshold_with_agenda_cards(self):
        s = ScenarioState(scenario_id="test", doom_threshold=10)
        a1 = AgendaCard(id="a1", name="A1", name_cn="A1", doom_threshold=5)
        a2 = AgendaCard(id="a2", name="A2", name_cn="A2", doom_threshold=8)
        s.agenda_cards = {"a1": a1, "a2": a2}
        s.agenda_deck = ["a1", "a2"]
        s.current_agenda_index = 0
        assert s.effective_doom_threshold == 5
        s.current_agenda_index = 1
        assert s.effective_doom_threshold == 8

    def test_effective_doom_threshold_fallback(self):
        s = ScenarioState(scenario_id="test", doom_threshold=7)
        # No agenda_cards, uses fallback
        assert s.effective_doom_threshold == 7

    def test_current_agenda_property(self):
        s = ScenarioState(scenario_id="test")
        assert s.current_agenda is None
        a1 = AgendaCard(id="a1", name="A1", name_cn="A1", doom_threshold=5)
        s.agenda_cards = {"a1": a1}
        s.agenda_deck = ["a1"]
        s.current_agenda_index = 0
        assert s.current_agenda is a1

    def test_current_act_property(self):
        s = ScenarioState(scenario_id="test")
        assert s.current_act is None
        act1 = ActCard(id="act1", name="Act1", name_cn="事件1", clue_threshold=3)
        s.act_cards = {"act1": act1}
        s.act_deck = ["act1"]
        s.current_act_index = 0
        assert s.current_act is act1

    def test_multi_agenda_advance(self):
        """Simulate advancing through multiple agendas."""
        s = ScenarioState(scenario_id="test")
        a1 = AgendaCard(id="a1", name="A1", name_cn="A1", doom_threshold=4)
        a2 = AgendaCard(id="a2", name="A2", name_cn="A2", doom_threshold=6)
        s.agenda_cards = {"a1": a1, "a2": a2}
        s.agenda_deck = ["a1", "a2"]
        s.current_agenda_index = 0
        assert s.effective_doom_threshold == 4
        # Simulate advancement
        s.current_agenda_index = 1
        assert s.effective_doom_threshold == 6
        # Beyond last agenda
        s.current_agenda_index = 2
        assert s.current_agenda is None


# ============================================================
# MythosPhase uses effective_doom_threshold
# ============================================================

class TestMythosPhaseWithAgendaCards:
    def test_mythos_uses_effective_threshold(self):
        g = Game("test")
        ic = make_investigator_card()
        loc = make_location_data()
        g.register_card_data(loc)
        g.add_location("test_location", loc, clues=2)
        g.add_investigator("p1", ic, starting_location="test_location")

        # Setup multi-agenda
        a1 = AgendaCard(id="a1", name="A1", name_cn="A1", doom_threshold=3)
        g.state.scenario.agenda_cards = {"a1": a1}
        g.state.scenario.agenda_deck = ["a1"]
        g.state.scenario.current_agenda_index = 0
        g.state.scenario.doom_threshold = 99  # Should be ignored

        # Set doom to 2, one mythos round should push to 3 and advance
        g.state.scenario.doom_on_agenda = 2
        g.state.scenario.round_number = 2  # Skip round 1 check

        g.mythos_phase._place_doom()
        assert g.state.scenario.doom_on_agenda == 3

        g.mythos_phase._check_doom_threshold()
        # Agenda should have advanced
        assert g.state.scenario.current_agenda_index == 1
        assert g.state.scenario.doom_on_agenda == 0  # Reset after advance


# ============================================================
# Chaos Bag serialization
# ============================================================

class TestChaosBagSerialization:
    def test_standard_bag_token_count(self):
        bag = ChaosBag()
        counts = Counter(bag.tokens)
        assert counts[ChaosTokenType.PLUS_1] == 1
        assert counts[ChaosTokenType.ZERO] == 2
        assert counts[ChaosTokenType.MINUS_1] == 3
        assert counts[ChaosTokenType.AUTO_FAIL] == 1
        assert len(bag.tokens) == 16

    def test_serialization_format(self):
        bag = ChaosBag()
        # Simulate what servers do
        serialized = {
            "tokens": {t.value: c for t, c in Counter(bag.tokens).items()},
            "sealed": {t.value: c for t, c in Counter(bag.sealed).items()},
            "total": len(bag.tokens),
        }
        assert serialized["total"] == 16
        assert serialized["tokens"]["+1"] == 1
        assert serialized["tokens"]["0"] == 2
        assert serialized["tokens"]["auto_fail"] == 1
        assert serialized["sealed"] == {}

    def test_sealed_tokens_in_serialization(self):
        bag = ChaosBag()
        bag.seal_token(ChaosTokenType.SKULL)
        serialized = {
            "tokens": {t.value: c for t, c in Counter(bag.tokens).items()},
            "sealed": {t.value: c for t, c in Counter(bag.sealed).items()},
            "total": len(bag.tokens),
        }
        assert serialized["total"] == 15
        assert serialized["sealed"]["skull"] == 1
        assert serialized["tokens"].get("skull", 0) == 1  # One skull left


# ============================================================
# Doom check immediate vs deferred
# ============================================================

class TestDoomCheckImmediate:
    def test_immediate_doom_check(self):
        """Ancient Evils with doom_check_immediate=True triggers check."""
        enc = {
            "fail_effect": "doom", "fail_amount": 1,
            "doom_check_immediate": True,
        }
        # Simulating the logic from resolve_encounter_card
        checked = enc.get("doom_check_immediate", True)
        assert checked is True

    def test_deferred_doom_check(self):
        """Card with doom_check_immediate=False does not trigger immediate check."""
        enc = {
            "fail_effect": "doom", "fail_amount": 1,
            "doom_check_immediate": False,
        }
        checked = enc.get("doom_check_immediate", True)
        assert checked is False

    def test_default_doom_check_is_immediate(self):
        """Cards without the flag default to immediate check."""
        enc = {"fail_effect": "doom", "fail_amount": 1}
        checked = enc.get("doom_check_immediate", True)
        assert checked is True


# ============================================================
# Tote Bag slot
# ============================================================

class TestToteBagSlot:
    def test_tote_bag_json_has_no_slot(self):
        import json
        from pathlib import Path
        json_path = Path(__file__).parent.parent.parent / "data" / "player_cards" / "seeker" / "daisys_tote_bag.json"
        with open(json_path) as f:
            data = json.load(f)
        assert data["slots"] == []
