"""Tests for Serpents of Yig & Shadow Agents (Level 0) — enemy signature weaknesses."""

from backend.cards.neutral.serpents_of_yig_lv0 import SerpentsOfYig
from backend.cards.neutral.shadow_agents_lv0 import ShadowAgents
from backend.engine.event_bus import EventContext
from backend.models.chaos import ChaosBag
from backend.models.enums import ChaosTokenType, GameEvent
from backend.models.state import CardInstance


def _emit(game, event, **kwargs):
    ctx = EventContext(
        game_state=game.state, event=event,
        investigator_id=kwargs.pop("inv_id", "test_investigator"), **kwargs,
    )
    game.event_bus.emit(ctx)
    return ctx


class TestSerpentsOfYig:
    def _register_with_bag(self, game, tokens):
        bag = ChaosBag(tokens=list(tokens))
        bag.seed(1)
        impl = SerpentsOfYig("soy_1")
        impl.register(game.event_bus, "soy_1")
        impl.bind_chaos_bag(bag)
        return impl, bag

    def test_revelation_seals_elder_sign(self, game):
        """显现：从混沌袋封印[远古印记]。"""
        impl, bag = self._register_with_bag(
            game, [ChaosTokenType.ELDER_SIGN, ChaosTokenType.SKULL])
        inv = game.state.get_investigator("test_investigator")
        inv.hand.append("serpents_of_yig_lv0")

        ctx = _emit(game, GameEvent.CARD_DRAWN,
                    extra={"card_id": "serpents_of_yig_lv0"})
        assert ctx.extra["serpents_of_yig_sealed_elder_sign"] is True
        assert ChaosTokenType.ELDER_SIGN in bag.sealed
        assert ChaosTokenType.ELDER_SIGN not in bag.tokens
        assert game.state.scenario.vars["serpents_of_yig_sealed"] is True

    def test_release_on_defeat(self, game):
        """被击败：远古印记释回混沌袋。"""
        impl, bag = self._register_with_bag(
            game, [ChaosTokenType.ELDER_SIGN, ChaosTokenType.SKULL])
        inv = game.state.get_investigator("test_investigator")
        inv.hand.append("serpents_of_yig_lv0")
        _emit(game, GameEvent.CARD_DRAWN, extra={"card_id": "serpents_of_yig_lv0"})

        _emit(game, GameEvent.ENEMY_DEFEATED, target="soy_enemy",
              extra={"card_id": "serpents_of_yig_lv0"})
        assert ChaosTokenType.ELDER_SIGN in bag.tokens
        assert ChaosTokenType.ELDER_SIGN not in bag.sealed
        assert "serpents_of_yig_sealed" not in game.state.scenario.vars

    def test_no_elder_sign_in_bag_is_noop(self, game):
        """袋中无远古印记：不触发。"""
        impl, bag = self._register_with_bag(game, [ChaosTokenType.SKULL])
        inv = game.state.get_investigator("test_investigator")
        inv.hand.append("serpents_of_yig_lv0")
        ctx = _emit(game, GameEvent.CARD_DRAWN,
                    extra={"card_id": "serpents_of_yig_lv0"})
        assert "serpents_of_yig_sealed_elder_sign" not in ctx.extra


class TestShadowAgents:
    def _spawn(self, game):
        from backend.tests.conftest import make_enemy_data
        game.register_card_data(make_enemy_data(id="shadow_agents_lv0", name="Shadow Agents"))
        enemy = CardInstance(
            instance_id="sa_1", card_id="shadow_agents_lv0",
            owner_id="test_investigator", controller_id="scenario",
        )
        game.state.cards_in_play["sa_1"] = enemy
        inv = game.state.get_investigator("test_investigator")
        inv.threat_area.append("sa_1")
        return enemy

    def test_discarded_after_evaded(self, game):
        """强制 - 被躲避后：丢弃（回持有者弃牌堆）。"""
        impl = ShadowAgents("sa_impl")
        impl.register(game.event_bus, "sa_impl")
        self._spawn(game)
        inv = game.state.get_investigator("test_investigator")
        loc = game.state.locations["test_location"]

        # 模拟躲避结算：横置并放到地点（引擎 on_success 已做），再发事件
        enemy = game.state.get_card_instance("sa_1")
        enemy.exhausted = True
        inv.threat_area.remove("sa_1")
        loc.enemies.append("sa_1")

        ctx = _emit(game, GameEvent.ENEMY_EVADED, enemy_id="sa_1")
        assert ctx.extra["shadow_agents_discarded"] is True
        assert "sa_1" not in loc.enemies
        assert game.state.get_card_instance("sa_1") is None
        assert "shadow_agents_lv0" in inv.discard

    def test_clue_discovery_restriction(self, game):
        """交战时：仅能通过调查发现线索。"""
        impl = ShadowAgents("sa_impl")
        impl.register(game.event_bus, "sa_impl")
        self._spawn(game)
        assert impl.can_discover_clues(game.state, "test_investigator") is False
        assert impl.can_discover_clues(
            game.state, "test_investigator", by_investigating=True) is True
