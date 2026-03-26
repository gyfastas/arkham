"""Tests for Zoey Samaras investigator ability."""

import pytest
from backend.cards.guardian.zoey_samaras import ZoeySamaras
from backend.engine.event_bus import EventBus, EventContext
from backend.engine.game import Game
from backend.models.enums import (
    Action, CardType, ChaosTokenType, GameEvent, Phase, PlayerClass,
)
from backend.models.state import CardData, CardInstance, SkillValues


def _make_zoey_data():
    return CardData(
        id="zoey_samaras", name="Zoey Samaras", name_cn="佐伊·萨马拉斯",
        type=CardType.INVESTIGATOR, card_class=PlayerClass.GUARDIAN,
        health=9, sanity=6,
        skills=SkillValues(willpower=4, intellect=2, combat=4, agility=2),
        ability="[reaction] After you become engaged with an enemy: Gain 1 resource.",
    )


def _make_enemy_data(enemy_id="test_enemy"):
    return CardData(
        id=enemy_id, name="Test Enemy", name_cn="测试敌人",
        type=CardType.ENEMY, card_class=PlayerClass.NEUTRAL,
        enemy_damage=1, enemy_horror=1, enemy_fight=2, enemy_evade=2,
        health=2, traits=["human"],
    )


@pytest.fixture
def game():
    g = Game("test_zoey")
    g.chaos_bag.seed(42)

    zoey_data = _make_zoey_data()
    g.register_card_data(zoey_data)

    loc_data = CardData(
        id="test_location", name="Test Location", name_cn="测试地点",
        type=CardType.LOCATION, card_class=PlayerClass.NEUTRAL,
    )
    g.register_card_data(loc_data)

    enemy_data = _make_enemy_data()
    g.register_card_data(enemy_data)

    deck = ["card_a", "card_b", "card_c", "card_d", "card_e"] * 3
    g.add_investigator("zoey", zoey_data, deck=deck, starting_location="test_location")
    g.add_location("test_location", loc_data, clues=0)

    # Register Zoey's ability
    g.card_registry.register_class(ZoeySamaras)

    return g


class TestZoeySamaras:
    def test_ability_gains_resource_when_engaged(self, game):
        """Zoey gains 1 resource when she becomes engaged with an enemy (via pending choice)."""
        inv = game.state.get_investigator("zoey")
        initial_resources = inv.resources

        # Register Zoey's ability
        zoey_impl = ZoeySamaras("zoey_impl")
        zoey_impl.register(game.event_bus, "zoey_impl")

        # Create an enemy at the location
        enemy_iid = game.state.next_instance_id()
        enemy = CardInstance(
            instance_id=enemy_iid, card_id="test_enemy",
            owner_id="zoey", controller_id="zoey",
        )
        game.state.cards_in_play[enemy_iid] = enemy
        game.state.locations["test_location"].enemies.append(enemy_iid)

        # Emit ENEMY_ENGAGED event (as if enemy engaged with Zoey)
        ctx = EventContext(
            game_state=game.state,
            event=GameEvent.ENEMY_ENGAGED,
            investigator_id="zoey",
            enemy_id=enemy_iid,
        )
        game.event_bus.emit(ctx)

        # Should set up pending choice instead of auto-triggering
        pending = game.state.scenario.vars.get("pending_choice")
        assert pending is not None
        assert pending["kind"] == "zoey_reactions_on_engage"
        assert pending["investigator_id"] == "zoey"
        assert pending["enemy_id"] == enemy_iid

        # Simulate player choosing to gain resource
        game.state.scenario.vars.pop("pending_choice", None)
        inv.resources += 1

        # Should gain 1 resource
        assert inv.resources == initial_resources + 1

    def test_ability_does_not_trigger_for_other_investigators(self, game):
        """Zoey's ability does not trigger when other investigators engage enemies."""
        # Add another investigator
        other_data = CardData(
            id="roland_banks", name="Roland Banks", name_cn="罗兰·班克斯",
            type=CardType.INVESTIGATOR, card_class=PlayerClass.GUARDIAN,
            health=9, sanity=5,
            skills=SkillValues(willpower=3, intellect=3, combat=4, agility=2),
        )
        game.register_card_data(other_data)
        game.add_investigator("roland", other_data, deck=[], starting_location="test_location")

        inv = game.state.get_investigator("zoey")
        initial_resources = inv.resources

        # Register Zoey's ability
        zoey_impl = ZoeySamaras("zoey_impl")
        zoey_impl.register(game.event_bus, "zoey_impl")

        # Create an enemy
        enemy_iid = game.state.next_instance_id()
        enemy = CardInstance(
            instance_id=enemy_iid, card_id="test_enemy",
            owner_id="roland", controller_id="roland",
        )
        game.state.cards_in_play[enemy_iid] = enemy

        # Emit ENEMY_ENGAGED for Roland (not Zoey)
        ctx = EventContext(
            game_state=game.state,
            event=GameEvent.ENEMY_ENGAGED,
            investigator_id="roland",  # Not Zoey!
            enemy_id=enemy_iid,
        )
        game.event_bus.emit(ctx)

        # Zoey should NOT gain resources
        assert inv.resources == initial_resources

    def test_elder_sign_adds_plus_one(self, game):
        """Zoey's elder sign adds +1 to skill test."""
        inv = game.state.get_investigator("zoey")

        # Register Zoey's ability
        zoey_impl = ZoeySamaras("zoey_impl")
        zoey_impl.register(game.event_bus, "zoey_impl")

        # Create a skill test context with elder sign
        ctx = EventContext(
            game_state=game.state,
            event=GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="zoey",
            chaos_token=ChaosTokenType.ELDER_SIGN,
            extra={},
        )

        # Initial amount should be 0
        assert ctx.amount == 0

        # Emit the event
        game.event_bus.emit(ctx)

        # Should have +1 modifier
        assert ctx.amount == 1

    def test_elder_sign_only_triggers_for_zoey(self, game):
        """Elder sign effect only triggers for Zoey, not other investigators."""
        # Add another investigator
        other_data = CardData(
            id="roland_banks", name="Roland Banks", name_cn="罗兰·班克斯",
            type=CardType.INVESTIGATOR, card_class=PlayerClass.GUARDIAN,
            health=9, sanity=5,
            skills=SkillValues(willpower=3, intellect=3, combat=4, agility=2),
        )
        game.register_card_data(other_data)
        game.add_investigator("roland", other_data, deck=[], starting_location="test_location")

        # Register Zoey's ability
        zoey_impl = ZoeySamaras("zoey_impl")
        zoey_impl.register(game.event_bus, "zoey_impl")

        # Create a skill test context for Roland with elder sign
        ctx = EventContext(
            game_state=game.state,
            event=GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="roland",  # Not Zoey!
            chaos_token=ChaosTokenType.ELDER_SIGN,
            extra={},
        )

        # Emit the event
        game.event_bus.emit(ctx)

        # Should NOT have modifier for Roland
        assert ctx.amount == 0
