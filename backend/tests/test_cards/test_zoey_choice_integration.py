"""Integration test for Zoey Samaras engagement choice system."""

import pytest
from backend.cards.guardian.zoey_samaras import ZoeySamaras
from backend.cards.neutral.zoeys_cross_lv0 import ZoeysCross
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


def _make_cross_data():
    return CardData(
        id="zoeys_cross_lv0", name="Zoey's Cross", name_cn="佐伊的十字架",
        type=CardType.ASSET, card_class=PlayerClass.NEUTRAL,
        cost=1, slots=[],
        text="[reaction] After an enemy engages you: Exhaust and spend 1 resource to deal 1 damage.",
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
    """Create a game with Zoey and her cross."""
    g = Game("test_zoey_choice")
    g.chaos_bag.seed(42)

    zoey_data = _make_zoey_data()
    g.register_card_data(zoey_data)

    cross_data = _make_cross_data()
    g.register_card_data(cross_data)

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

    # Register card implementations
    g.card_registry.register_class(ZoeySamaras)
    g.card_registry.register_class(ZoeysCross)

    # Put cross in play for Zoey
    inv = g.state.get_investigator("zoey")
    inv.resources = 5  # Give her some resources

    cross_iid = g.state.next_instance_id()
    cross_instance = CardInstance(
        instance_id=cross_iid, card_id="zoeys_cross_lv0",
        owner_id="zoey", controller_id="zoey",
    )
    g.state.cards_in_play[cross_iid] = cross_instance
    inv.play_area.append(cross_iid)

    # Set up scenario vars for pending_choice
    if g.state.scenario.vars is None:
        g.state.scenario.vars = {}

    return g


class TestZoeyEngagementChoice:
    """Test Zoey's engagement choice system."""

    def test_pending_choice_set_on_engage(self, game):
        """When enemy engages, pending_choice should be set."""
        inv = game.state.get_investigator("zoey")

        # Ensure scenario.vars is initialized
        if game.state.scenario.vars is None:
            game.state.scenario.vars = {}

        # Create an enemy
        enemy_iid = game.state.next_instance_id()
        enemy = CardInstance(
            instance_id=enemy_iid, card_id="test_enemy",
            owner_id="zoey", controller_id="zoey",
        )
        game.state.cards_in_play[enemy_iid] = enemy
        game.state.locations["test_location"].enemies.append(enemy_iid)

        # Register Zoey's ability to the event bus
        zoey_impl = ZoeySamaras("zoey_impl")
        zoey_impl.register(game.event_bus, "zoey_impl")

        # Emit ENEMY_ENGAGED event
        ctx = EventContext(
            game_state=game.state,
            event=GameEvent.ENEMY_ENGAGED,
            investigator_id="zoey",
            enemy_id=enemy_iid,
        )
        game.event_bus.emit(ctx)

        # Check pending_choice was set
        pending = game.state.scenario.vars.get("pending_choice")
        assert pending is not None, "pending_choice should be set after ENEMY_ENGAGED event"
        assert pending["kind"] == "zoey_reactions_on_engage"
        assert pending["investigator_id"] == "zoey"
        assert pending["enemy_id"] == enemy_iid
        assert pending["cross_usable"] is True  # Cross is in play and ready
        assert len(pending["options"]) == 4  # resource, cross, both, none

    def test_choice_resource_only_gains_resource(self, game):
        """Choosing 'resource' should only gain 1 resource."""
        inv = game.state.get_investigator("zoey")
        initial_resources = inv.resources

        # Set up pending choice
        enemy_iid = "test_enemy_1"
        cross_iid = inv.play_area[0]

        game.state.scenario.vars["pending_choice"] = {
            "kind": "zoey_reactions_on_engage",
            "enemy_id": enemy_iid,
            "enemy_name": "测试敌人",
            "investigator_id": "zoey",
            "cross_usable": True,
            "cross_instance_id": cross_iid,
            "options": [
                {"id": "resource", "label": "获得1资源"},
                {"id": "cross", "label": "使用十字架"},
                {"id": "both", "label": "两者都触发"},
                {"id": "none", "label": "都不触发"},
            ],
        }

        # Simulate resolving the choice
        from server.game_session import GameSession
        session = GameSession.__new__(GameSession)
        session.game = game
        session.controller = None
        session.action_log = []

        result = session._resolve_choice({"choice_id": "resource"})

        assert result["success"] is True
        assert inv.resources == initial_resources + 1

    def test_choice_cross_uses_cross(self, game):
        """Choosing 'cross' should exhaust cross and deal damage."""
        inv = game.state.get_investigator("zoey")
        initial_resources = inv.resources

        # Create enemy in threat area
        enemy_iid = game.state.next_instance_id()
        enemy_data = _make_enemy_data()
        game.register_card_data(enemy_data)

        enemy = CardInstance(
            instance_id=enemy_iid, card_id="test_enemy",
            owner_id="zoey", controller_id="zoey",
        )
        game.state.cards_in_play[enemy_iid] = enemy
        inv.threat_area.append(enemy_iid)

        cross_iid = inv.play_area[0]
        cross_instance = game.state.get_card_instance(cross_iid)

        game.state.scenario.vars["pending_choice"] = {
            "kind": "zoey_reactions_on_engage",
            "enemy_id": enemy_iid,
            "enemy_name": "测试敌人",
            "investigator_id": "zoey",
            "cross_usable": True,
            "cross_instance_id": cross_iid,
            "options": [
                {"id": "resource", "label": "获得1资源"},
                {"id": "cross", "label": "使用十字架"},
                {"id": "both", "label": "两者都触发"},
                {"id": "none", "label": "都不触发"},
            ],
        }

        from server.game_session import GameSession
        session = GameSession.__new__(GameSession)
        session.game = game
        session.controller = None
        session.action_log = []

        result = session._resolve_choice({"choice_id": "cross"})

        assert result["success"] is True
        # Should spend 1 resource
        assert inv.resources == initial_resources - 1
        # Cross should be exhausted
        assert cross_instance.exhausted is True
        # Enemy should take 1 damage
        assert enemy.damage == 1

    def test_choice_both_triggers_both(self, game):
        """Choosing 'both' should trigger both abilities."""
        inv = game.state.get_investigator("zoey")
        initial_resources = inv.resources

        # Create enemy in threat area
        enemy_iid = game.state.next_instance_id()
        enemy_data = _make_enemy_data()
        game.register_card_data(enemy_data)

        enemy = CardInstance(
            instance_id=enemy_iid, card_id="test_enemy",
            owner_id="zoey", controller_id="zoey",
        )
        game.state.cards_in_play[enemy_iid] = enemy
        inv.threat_area.append(enemy_iid)

        cross_iid = inv.play_area[0]
        cross_instance = game.state.get_card_instance(cross_iid)

        game.state.scenario.vars["pending_choice"] = {
            "kind": "zoey_reactions_on_engage",
            "enemy_id": enemy_iid,
            "enemy_name": "测试敌人",
            "investigator_id": "zoey",
            "cross_usable": True,
            "cross_instance_id": cross_iid,
            "options": [
                {"id": "resource", "label": "获得1资源"},
                {"id": "cross", "label": "使用十字架"},
                {"id": "both", "label": "两者都触发"},
                {"id": "none", "label": "都不触发"},
            ],
        }

        from server.game_session import GameSession
        session = GameSession.__new__(GameSession)
        session.game = game
        session.controller = None
        session.action_log = []

        result = session._resolve_choice({"choice_id": "both"})

        assert result["success"] is True
        # Net resources: +1 (ability) -1 (cross cost) = 0 change
        assert inv.resources == initial_resources
        # Cross should be exhausted
        assert cross_instance.exhausted is True
        # Enemy should take 1 damage
        assert enemy.damage == 1

    def test_choice_none_does_nothing(self, game):
        """Choosing 'none' should not trigger any abilities."""
        inv = game.state.get_investigator("zoey")
        initial_resources = inv.resources

        cross_iid = inv.play_area[0]
        cross_instance = game.state.get_card_instance(cross_iid)
        initial_exhausted = cross_instance.exhausted

        game.state.scenario.vars["pending_choice"] = {
            "kind": "zoey_reactions_on_engage",
            "enemy_id": "test_enemy",
            "enemy_name": "测试敌人",
            "investigator_id": "zoey",
            "cross_usable": True,
            "cross_instance_id": cross_iid,
            "options": [
                {"id": "resource", "label": "获得1资源"},
                {"id": "cross", "label": "使用十字架"},
                {"id": "both", "label": "两者都触发"},
                {"id": "none", "label": "都不触发"},
            ],
        }

        from server.game_session import GameSession
        session = GameSession.__new__(GameSession)
        session.game = game
        session.controller = None
        session.action_log = []

        result = session._resolve_choice({"choice_id": "none"})

        assert result["success"] is True
        # Resources unchanged
        assert inv.resources == initial_resources
        # Cross state unchanged
        assert cross_instance.exhausted == initial_exhausted
