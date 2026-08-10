"""Tests for Purifying Corruption (Level 4)."""

from backend.cards.neutral.purifying_corruption_lv4 import PurifyingCorruption
from backend.engine.event_bus import EventContext
from backend.models.enums import CardType, GameEvent, PlayerClass
from backend.models.state import CardData, CardInstance


def _setup(game):
    """装备净化腐蚀并注册实现；登记一张非弱点诡计卡数据。"""
    treachery = CardData(
        id="weak_treachery", name="Some Treachery", name_cn="某诡计",
        type=CardType.TREACHERY, card_class=PlayerClass.MYSTIC,
    )
    game.register_card_data(treachery)
    enemy = CardData(
        id="enc_enemy", name="Enc Enemy", name_cn="遭遇敌人",
        type=CardType.ENEMY, enemy_fight=3, enemy_health=3, enemy_evade=3,
    )
    game.register_card_data(enemy)

    inv = game.state.get_investigator("test_investigator")
    ci = CardInstance(
        instance_id="pc_1", card_id="purifying_corruption_lv4",
        owner_id="test_investigator", controller_id="test_investigator",
    )
    game.state.cards_in_play["pc_1"] = ci
    inv.play_area.append("pc_1")
    impl = PurifyingCorruption("pc_1")
    impl.register(game.event_bus, "pc_1")
    return impl


def _draw_encounter(game, card_id):
    ctx = EventContext(
        game_state=game.state,
        event=GameEvent.ENCOUNTER_CARD_DRAWN,
        investigator_id="test_investigator",
        extra={"card_id": card_id},
    )
    game.event_bus.emit(ctx)
    return ctx


class TestPurifyingCorruption:
    def test_cancels_treachery_and_gains_corruption(self, game):
        """抽非弱点诡计：受1伤1恐，取消显现，放置1腐蚀。"""
        _setup(game)
        inv = game.state.get_investigator("test_investigator")

        ctx = _draw_encounter(game, "weak_treachery")
        assert inv.damage == 1
        assert inv.horror == 1
        assert game.state.scenario.vars["cancelled_encounter"] == "weak_treachery"
        assert ctx.extra["purifying_corruption_cancelled"] == "weak_treachery"
        inst = game.state.get_card_instance("pc_1")
        assert inst.uses["corruption"] == 1

    def test_no_trigger_for_enemy(self, game):
        """非诡计卡不触发。"""
        _setup(game)
        inv = game.state.get_investigator("test_investigator")
        _draw_encounter(game, "enc_enemy")
        assert inv.damage == 0 and inv.horror == 0

    def test_removed_at_three_corruption(self, game):
        """3个腐蚀：从游戏中移除。"""
        _setup(game)
        for _ in range(3):
            _draw_encounter(game, "weak_treachery")
        assert game.state.get_card_instance("pc_1") is None
        inv = game.state.get_investigator("test_investigator")
        assert "pc_1" not in inv.play_area
        assert "purifying_corruption_lv4" in game.state.scenario.vars["removed_from_game"]

    def test_fast_heal_draws_encounter(self, game):
        """[fast] 抽遭遇牌堆顶并治疗1伤害1恐惧。"""
        impl = _setup(game)
        inv = game.state.get_investigator("test_investigator")
        inv.damage = 2
        inv.horror = 2
        game.state.scenario.encounter_deck = ["enc_enemy"]

        drawn = impl.activate(game.state, "test_investigator", mode="heal")
        assert drawn == "enc_enemy"
        assert inv.damage == 1 and inv.horror == 1
        assert game.state.scenario.encounter_deck == []

    def test_fast_remove_corruption(self, game):
        """[fast] 改为移除1腐蚀。"""
        impl = _setup(game)
        inst = game.state.get_card_instance("pc_1")
        inst.uses["corruption"] = 2
        drawn = impl.activate(game.state, "test_investigator", mode="remove")
        assert drawn is None  # 遭遇牌堆为空
        assert inst.uses["corruption"] == 1
