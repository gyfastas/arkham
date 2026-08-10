"""Tests for The Council's Coffer (Level 2)."""

from backend.cards.neutral.the_councils_coffer_lv2 import TheCouncilsCoffer
from backend.engine.event_bus import EventContext
from backend.models.enums import GameEvent, Skill
from backend.models.state import CardInstance
from backend.tests.conftest import make_asset_data, make_investigator_data


def _equip(game):
    inv = game.state.get_investigator("test_investigator")
    ci = CardInstance(
        instance_id="coffer_1", card_id="the_councils_coffer_lv2",
        owner_id="test_investigator", controller_id="test_investigator",
    )
    game.state.cards_in_play["coffer_1"] = ci
    inv.play_area.append("coffer_1")
    impl = TheCouncilsCoffer("coffer_1")
    impl.register(game.event_bus, "coffer_1")
    game.event_bus.emit(EventContext(
        game_state=game.state, event=GameEvent.CARD_ENTERS_PLAY,
        investigator_id="test_investigator", target="coffer_1",
        extra={"card_id": "the_councils_coffer_lv2"},
    ))
    return impl


def _skill_success(game, inv_id="test_investigator"):
    ctx = EventContext(
        game_state=game.state, event=GameEvent.SKILL_TEST_SUCCESSFUL,
        investigator_id=inv_id, skill_type=Skill.WILLPOWER,
        success=True, modified_skill=6, difficulty=5,
    )
    game.event_bus.emit(ctx)
    return ctx


class TestTheCouncilsCoffer:
    def test_locks_init_per_investigator(self, game):
        """进场：1锁/每名调查员。"""
        _equip(game)
        inst = game.state.get_card_instance("coffer_1")
        assert inst.uses["locks"] == 1

    def test_locks_init_two_investigators(self, game):
        other = make_investigator_data(id="inv2", name="Inv2")
        game.register_card_data(other)
        game.add_investigator("inv2", other, starting_location="test_location")
        _equip(game)
        inst = game.state.get_card_instance("coffer_1")
        assert inst.uses["locks"] == 2

    def test_unlock_success_removes_lock_and_pays_off(self, game):
        """开锁检定成功：移除最后的锁 → 免费打出检索卡并放逐。"""
        impl = _equip(game)
        inv = game.state.get_investigator("test_investigator")
        game.register_card_data(make_asset_data(id="leather_coat_lv0", cost=2))
        inv.deck = ["leather_coat_lv0"]
        resources_before = inv.resources

        assert impl.activate_unlock(game.state, "test_investigator") is True
        ctx = _skill_success(game)
        assert ctx.extra["councils_coffer_lock_removed"] is True

        # 免费打出（不扣资源）
        assert inv.resources == resources_before
        assert "leather_coat_lv0" not in inv.deck
        played = game.state.scenario.vars["councils_coffer_played"]
        assert played == {"test_investigator": "leather_coat_lv0"}
        new_iid = [i for i in inv.play_area if i != "coffer_1"]
        assert len(new_iid) == 1

        # 金库被放逐
        assert game.state.get_card_instance("coffer_1") is None
        assert "the_councils_coffer_lv2" in game.state.scenario.vars["exiled_cards"]
        assert game.state.scenario.vars["councils_coffer_used"] is True

    def test_failed_test_keeps_lock(self, game):
        """检定失败：锁保留。"""
        impl = _equip(game)
        assert impl.activate_unlock(game.state, "test_investigator") is True
        ctx = EventContext(
            game_state=game.state, event=GameEvent.SKILL_TEST_FAILED,
            investigator_id="test_investigator", skill_type=Skill.COMBAT,
            success=False, modified_skill=2, difficulty=5,
        )
        game.event_bus.emit(ctx)
        inst = game.state.get_card_instance("coffer_1")
        assert inst.uses["locks"] == 1
