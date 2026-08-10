"""Tests for Daisy Walker investigator + signature cards."""

import pytest
from backend.cards.seeker.daisy_walker import DaisyWalker
from backend.cards.seeker.daisys_tote_bag import DaisysToteBag
from backend.cards.neutral.the_necronomicon import TheNecronomicon
from backend.engine.event_bus import EventBus, EventContext
from backend.engine.game import Game
from backend.models.enums import (
    Action, CardType, ChaosTokenType, GameEvent, Phase, PlayerClass, SlotType,
)
from backend.models.state import CardData, CardInstance, InvestigatorState, SkillValues


def _make_daisy_data():
    return CardData(
        id="daisy_walker", name="Daisy Walker", name_cn="黛西·沃克",
        type=CardType.INVESTIGATOR, card_class=PlayerClass.SEEKER,
        health=5, sanity=9,
        skills=SkillValues(willpower=3, intellect=5, combat=2, agility=2),
        ability="Extra Tome action.",
    )


@pytest.fixture
def game():
    from backend.tests.conftest import make_location_data
    g = Game("test_daisy")
    g.chaos_bag.seed(42)

    daisy_data = _make_daisy_data()
    g.register_card_data(daisy_data)

    loc = make_location_data()
    g.register_card_data(loc)

    deck = ["card_a", "card_b", "card_c", "card_d", "card_e"] * 3
    g.add_investigator("daisy", daisy_data, deck=deck, starting_location="test_location")
    g.add_location("test_location", loc, clues=3)

    g.card_registry.register_class(DaisyWalker)
    g.card_registry.register_class(DaisysToteBag)
    g.card_registry.register_class(TheNecronomicon)

    return g


class TestDaisyWalker:
    def test_stats(self, game):
        inv = game.state.get_investigator("daisy")
        assert inv.health == 5
        assert inv.sanity == 9
        assert inv.card_data.skills.intellect == 5
        assert inv.card_data.skills.combat == 2

    def test_tome_action_bonus(self, game):
        """Daisy gets 1 tome-only extra action; regular actions stay at 3."""
        inv = game.state.get_investigator("daisy")
        inv.actions_remaining = 3

        # Register Daisy's ability
        daisy_impl = DaisyWalker("daisy_impl")
        daisy_impl.register(game.event_bus, "daisy_impl")

        # Emit investigation phase begins
        ctx = EventContext(
            game_state=game.state,
            event=GameEvent.INVESTIGATION_PHASE_BEGINS,
            investigator_id="daisy",
        )
        game.event_bus.emit(ctx)

        assert inv.tome_actions_remaining == 1  # 1 tome-only action
        assert inv.actions_remaining == 3  # regular actions unchanged

    def test_elder_sign_draws_per_tome(self, game):
        """Elder sign: +0; on success draw 1 card per Tome controlled."""
        inv = game.state.get_investigator("daisy")
        hand_before = len(inv.hand)

        # Put a tome asset in play
        tome_data = CardData(
            id="old_book_of_lore_lv0", name="Old Book of Lore", name_cn="智慧古书",
            type=CardType.ASSET, card_class=PlayerClass.SEEKER, cost=3,
            slots=[SlotType.HAND], traits=["item", "tome"],
        )
        game.register_card_data(tome_data)
        ci = CardInstance(
            instance_id="tome_1", card_id="old_book_of_lore_lv0",
            owner_id="daisy", controller_id="daisy",
        )
        game.state.cards_in_play["tome_1"] = ci
        inv.play_area.append("tome_1")

        daisy_impl = DaisyWalker("daisy_impl")
        daisy_impl.register(game.event_bus, "daisy_impl")

        # Elder sign resolved during a successful test
        game.event_bus.emit(EventContext(
            game_state=game.state,
            event=GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="daisy",
            chaos_token=ChaosTokenType.ELDER_SIGN,
            amount=0,
        ))
        game.event_bus.emit(EventContext(
            game_state=game.state,
            event=GameEvent.SKILL_TEST_SUCCESSFUL,
            investigator_id="daisy",
            success=True,
        ))
        assert len(inv.hand) == hand_before + 1  # 1 tome -> draw 1

    def test_elder_sign_no_draw_on_failure(self, game):
        """Elder sign on a failed test draws nothing."""
        inv = game.state.get_investigator("daisy")
        hand_before = len(inv.hand)

        daisy_impl = DaisyWalker("daisy_impl")
        daisy_impl.register(game.event_bus, "daisy_impl")

        game.event_bus.emit(EventContext(
            game_state=game.state,
            event=GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="daisy",
            chaos_token=ChaosTokenType.ELDER_SIGN,
            amount=0,
        ))
        game.event_bus.emit(EventContext(
            game_state=game.state,
            event=GameEvent.SKILL_TEST_FAILED,
            investigator_id="daisy",
            success=False,
        ))
        game.event_bus.emit(EventContext(
            game_state=game.state,
            event=GameEvent.SKILL_TEST_ENDS,
            investigator_id="daisy",
            success=False,
        ))
        assert len(inv.hand) == hand_before


class TestDaisysToteBag:
    def test_enters_play_with_tome_slots(self, game):
        """Tote Bag grants 2 Tome-ONLY bonus hand slots (restricted)."""
        tote_data = CardData(
            id="daisys_tote_bag", name="Daisy's Tote Bag", name_cn="黛西的手提包",
            type=CardType.ASSET, card_class=PlayerClass.SEEKER, cost=2,
            slots=[], traits=["item"],
            unique=True,
        )
        game.register_card_data(tote_data)

        inv = game.state.get_investigator("daisy")
        inst_id = game.state.next_instance_id()
        ci = CardInstance(
            instance_id=inst_id, card_id="daisys_tote_bag",
            owner_id="daisy", controller_id="daisy",
        )
        game.state.cards_in_play[inst_id] = ci
        inv.play_area.append(inst_id)

        game.card_registry.activate_card("daisys_tote_bag", inst_id, game.event_bus)

        mgr = game.state.slot_managers["daisy"]
        assert mgr.effective_limit(SlotType.HAND, ["tome"]) == 2  # base only

        # Emit card enters play
        ctx = EventContext(
            game_state=game.state,
            event=GameEvent.CARD_ENTERS_PLAY,
            investigator_id="daisy",
            target=inst_id,
            extra={"card_id": "daisys_tote_bag"},
        )
        game.event_bus.emit(ctx)

        # Restricted bonus: tomes get 4 hand slots, non-tomes still only 2
        assert mgr.restricted_bonuses[SlotType.HAND][0]["count"] == 2
        assert mgr.restricted_bonuses[SlotType.HAND][0]["trait"] == "tome"
        assert mgr.effective_limit(SlotType.HAND, ["tome"]) == 4
        assert mgr.effective_limit(SlotType.HAND, ["item"]) == 2
        assert mgr.bonus_slots.get(SlotType.HAND) is None  # NOT a generic bonus
        assert ci.uses.get("tome_hand_slots") == 2

    def test_leaves_play_removes_slots(self, game):
        """Tote Bag leaving play removes the restricted bonus slots."""
        tote_data = CardData(
            id="daisys_tote_bag", name="Daisy's Tote Bag", name_cn="黛西的手提包",
            type=CardType.ASSET, card_class=PlayerClass.SEEKER, cost=2,
            slots=[], traits=["item"],
            unique=True,
        )
        game.register_card_data(tote_data)

        inv = game.state.get_investigator("daisy")
        inst_id = game.state.next_instance_id()
        ci = CardInstance(
            instance_id=inst_id, card_id="daisys_tote_bag",
            owner_id="daisy", controller_id="daisy",
        )
        game.state.cards_in_play[inst_id] = ci
        inv.play_area.append(inst_id)

        game.card_registry.activate_card("daisys_tote_bag", inst_id, game.event_bus)

        for evt in (GameEvent.CARD_ENTERS_PLAY, GameEvent.CARD_LEAVES_PLAY):
            game.event_bus.emit(EventContext(
                game_state=game.state,
                event=evt,
                investigator_id="daisy",
                target=inst_id,
                extra={"card_id": "daisys_tote_bag"},
            ))

        mgr = game.state.slot_managers["daisy"]
        assert SlotType.HAND not in mgr.restricted_bonuses
        assert mgr.effective_limit(SlotType.HAND, ["tome"]) == 2  # back to base


class TestTheNecronomicon:
    def test_revelation_puts_in_threat_area(self, game):
        """Drawing the Necronomicon puts it in threat area with 3 horror."""
        necro_data = CardData(
            id="the_necronomicon", name="The Necronomicon", name_cn="死灵之书",
            type=CardType.ASSET, card_class=PlayerClass.NEUTRAL,
            slots=[SlotType.HAND], traits=["item", "tome"],
            unique=True,
        )
        game.register_card_data(necro_data)

        inv = game.state.get_investigator("daisy")
        inv.hand.append("the_necronomicon")

        necro_impl = TheNecronomicon("necro_impl")
        necro_impl.register(game.event_bus, "necro_impl")

        # Emit card drawn event
        ctx = EventContext(
            game_state=game.state,
            event=GameEvent.CARD_DRAWN,
            investigator_id="daisy",
            extra={"card_id": "the_necronomicon"},
        )
        game.event_bus.emit(ctx)

        # Should be removed from hand
        assert "the_necronomicon" not in inv.hand
        # Should be in threat area
        assert len(inv.threat_area) == 1
        inst_id = inv.threat_area[0]
        ci = game.state.get_card_instance(inst_id)
        assert ci.card_id == "the_necronomicon"
        assert ci.uses["horror"] == 3

    def test_activate_moves_horror(self, game):
        """Activating Necronomicon moves 1 horror to investigator."""
        necro_data = CardData(
            id="the_necronomicon", name="The Necronomicon", name_cn="死灵之书",
            type=CardType.ASSET, card_class=PlayerClass.NEUTRAL,
            slots=[SlotType.HAND], traits=["item", "tome"],
        )
        game.register_card_data(necro_data)

        inv = game.state.get_investigator("daisy")
        inst_id = game.state.next_instance_id()
        ci = CardInstance(
            instance_id=inst_id, card_id="the_necronomicon",
            owner_id="daisy", controller_id="daisy",
        )
        ci.uses = {"horror": 3}
        game.state.cards_in_play[inst_id] = ci
        inv.threat_area.append(inst_id)

        necro_impl = TheNecronomicon(inst_id)
        necro_impl.register(game.event_bus, inst_id)

        old_horror = inv.horror
        result = necro_impl.activate(game.state, "daisy")
        assert result is True
        assert inv.horror == old_horror + 1
        assert ci.uses["horror"] == 2

    def test_elder_sign_treated_as_auto_fail(self, game):
        """死灵之书在威胁区域时，你揭示的[elder_sign]视为[auto_fail]。"""
        necro_data = CardData(
            id="the_necronomicon", name="The Necronomicon", name_cn="死灵之书",
            type=CardType.ASSET, card_class=PlayerClass.NEUTRAL,
            slots=[SlotType.HAND], traits=["item", "tome"],
        )
        game.register_card_data(necro_data)

        inv = game.state.get_investigator("daisy")
        inst_id = game.state.next_instance_id()
        ci = CardInstance(
            instance_id=inst_id, card_id="the_necronomicon",
            owner_id="daisy", controller_id="daisy",
        )
        ci.uses = {"horror": 3}
        game.state.cards_in_play[inst_id] = ci
        inv.threat_area.append(inst_id)

        necro_impl = TheNecronomicon(inst_id)
        necro_impl.register(game.event_bus, inst_id)

        ctx = EventContext(
            game_state=game.state,
            event=GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="daisy",
            chaos_token=ChaosTokenType.ELDER_SIGN,
            amount=0,
        )
        game.event_bus.emit(ctx)
        assert ctx.extra.get("force_auto_fail") is True

        # 其他标记不转换
        ctx2 = EventContext(
            game_state=game.state,
            event=GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="daisy",
            chaos_token=ChaosTokenType.SKULL,
            amount=-2,
        )
        game.event_bus.emit(ctx2)
        assert "force_auto_fail" not in ctx2.extra

    def test_discard_when_no_horror(self, game):
        """Necronomicon is discarded when last horror is moved off."""
        necro_data = CardData(
            id="the_necronomicon", name="The Necronomicon", name_cn="死灵之书",
            type=CardType.ASSET, card_class=PlayerClass.NEUTRAL,
            slots=[SlotType.HAND], traits=["item", "tome"],
        )
        game.register_card_data(necro_data)

        inv = game.state.get_investigator("daisy")
        inst_id = game.state.next_instance_id()
        ci = CardInstance(
            instance_id=inst_id, card_id="the_necronomicon",
            owner_id="daisy", controller_id="daisy",
        )
        ci.uses = {"horror": 1}
        game.state.cards_in_play[inst_id] = ci
        inv.threat_area.append(inst_id)

        necro_impl = TheNecronomicon(inst_id)
        necro_impl.register(game.event_bus, inst_id)

        necro_impl.activate(game.state, "daisy")

        # Should be removed from threat area and cards_in_play
        assert inst_id not in inv.threat_area
        assert inst_id not in game.state.cards_in_play
        assert "the_necronomicon" in inv.discard


class TestNecronomiconActionCost:
    """Necronomicon activation costs 1 action (official: [action], not free).
    Daisy may use her bonus Tome action since it has the Tome trait."""

    def _necro_in_threat(self, game):
        necro_data = CardData(
            id="the_necronomicon", name="The Necronomicon", name_cn="死灵之书",
            type=CardType.ASSET, card_class=PlayerClass.NEUTRAL,
            slots=[SlotType.HAND], traits=["item", "tome"],
        )
        game.register_card_data(necro_data)
        inv = game.state.get_investigator("daisy")
        inst_id = game.state.next_instance_id()
        ci = CardInstance(
            instance_id=inst_id, card_id="the_necronomicon",
            owner_id="daisy", controller_id="daisy",
        )
        ci.uses = {"horror": 3}
        game.state.cards_in_play[inst_id] = ci
        inv.threat_area.append(inst_id)
        game.card_registry.activate_card("the_necronomicon", inst_id, game.event_bus)
        return inst_id

    def _session(self, game):
        from server.game_session import GameSession
        s = GameSession.__new__(GameSession)
        s.game = game
        s.action_log = []
        s.controller = None
        s.game_over = None
        s.event_logger = None
        return s

    def test_activation_spends_tome_action_first(self, game):
        inst_id = self._necro_in_threat(game)
        inv = game.state.get_investigator("daisy")
        inv.actions_remaining = 3
        inv.tome_actions_remaining = 1

        s = self._session(game)
        result = s._activate_card(inv, {"instance_id": inst_id, "activation_id": "horror"})

        assert result["success"] is True
        assert inv.tome_actions_remaining == 0   # tome action used first
        assert inv.actions_remaining == 3        # regular actions untouched
        assert inv.horror == 1

    def test_activation_spends_regular_action_when_no_tome(self, game):
        inst_id = self._necro_in_threat(game)
        inv = game.state.get_investigator("daisy")
        inv.actions_remaining = 2
        inv.tome_actions_remaining = 0

        s = self._session(game)
        result = s._activate_card(inv, {"instance_id": inst_id, "activation_id": "horror"})

        assert result["success"] is True
        assert inv.actions_remaining == 1
        assert inv.horror == 1

    def test_activation_rejected_without_actions(self, game):
        inst_id = self._necro_in_threat(game)
        inv = game.state.get_investigator("daisy")
        inv.actions_remaining = 0
        inv.tome_actions_remaining = 0

        s = self._session(game)
        result = s._activate_card(inv, {"instance_id": inst_id, "activation_id": "horror"})

        assert result["success"] is False
        assert "行动" in result["message"]
        assert inv.horror == 0  # no horror moved
