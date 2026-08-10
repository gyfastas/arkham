"""Tests for Physical Training (Level 0)."""

from backend.cards.guardian.physical_training_lv0 import PhysicalTraining
from backend.engine.event_bus import EventContext
from backend.models.enums import GameEvent, Skill
from backend.models.state import CardInstance


def _setup(game):
    impl = PhysicalTraining("pt_1")
    impl.register(game.event_bus, "pt_1")
    pt = CardInstance(
        instance_id="pt_1", card_id="physical_training_lv0",
        owner_id="test_investigator", controller_id="test_investigator",
    )
    game.state.cards_in_play["pt_1"] = pt
    game.state.get_investigator("test_investigator").play_area.append("pt_1")
    return impl


def _skill_ctx(game, skill, amount):
    ctx = EventContext(
        game_state=game.state, event=GameEvent.SKILL_VALUE_DETERMINED,
        investigator_id="test_investigator", skill_type=skill, amount=amount,
    )
    game.event_bus.emit(ctx)
    return ctx


class TestPhysicalTraining:
    def test_card_id(self):
        assert PhysicalTraining.card_id == "physical_training_lv0"

    def test_spend_boosts_skill(self, game):
        """花1资源：本次检定+1战斗。"""
        impl = _setup(game)
        inv = game.state.get_investigator("test_investigator")
        inv.resources = 2

        assert impl.spend(game.state, "test_investigator", Skill.COMBAT) is True
        assert inv.resources == 1
        ctx = _skill_ctx(game, Skill.COMBAT, 3)
        assert ctx.amount == 4

    def test_multiple_spends_stack(self, game):
        """官方规则：同一检定可多次支付叠加（支付2次+2）。"""
        impl = _setup(game)
        inv = game.state.get_investigator("test_investigator")
        inv.resources = 3

        assert impl.spend(game.state, "test_investigator", Skill.WILLPOWER) is True
        assert impl.spend(game.state, "test_investigator", Skill.WILLPOWER) is True
        assert inv.resources == 1
        ctx = _skill_ctx(game, Skill.WILLPOWER, 2)
        assert ctx.amount == 4

    def test_boost_is_one_shot(self, game):
        """加值只作用于下一次检定。"""
        impl = _setup(game)
        inv = game.state.get_investigator("test_investigator")
        inv.resources = 2

        assert impl.spend(game.state, "test_investigator", Skill.COMBAT) is True
        assert _skill_ctx(game, Skill.COMBAT, 3).amount == 4
        assert _skill_ctx(game, Skill.COMBAT, 3).amount == 3
