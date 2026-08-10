"""Tests for signature & basic weakness card implementations."""

import pytest

from backend.cards.neutral.abandoned_and_alone import AbandonedAndAlone
from backend.cards.neutral.chronophobia_lv0 import Chronophobia
from backend.cards.neutral.cover_up import CoverUp
from backend.cards.neutral.dark_memory import DarkMemory
from backend.cards.neutral.final_rhapsody_lv0 import FinalRhapsody
from backend.cards.neutral.hospital_debts import HospitalDebts
from backend.cards.neutral.hypochondria import Hypochondria
from backend.cards.neutral.indebted_lv0 import Indebted
from backend.cards.neutral.internal_injury_lv0 import InternalInjury
from backend.cards.neutral.rexs_curse_lv0 import RexsCurse
from backend.cards.neutral.searching_for_izzie_lv0 import SearchingForIzzie
from backend.cards.neutral.smite_the_wicked_lv0 import SmiteTheWicked
from backend.cards.neutral.wracked_by_nightmares_lv0 import WrackedByNightmares
from backend.engine.event_bus import EventContext
from backend.models.chaos import ChaosBag
from backend.models.enums import ChaosTokenType, GameEvent
from backend.models.state import CardInstance
from backend.tests.conftest import make_enemy_data, make_location_data


def _emit(game, event, inv_id="test_investigator", **kwargs):
    ctx = EventContext(
        game_state=game.state, event=event, investigator_id=inv_id, **kwargs
    )
    game.event_bus.emit(ctx)
    return ctx


def _register(game, impl_cls, instance_id="weakness_impl"):
    impl = impl_cls(instance_id)
    impl.register(game.event_bus, instance_id)
    return impl


def _draw(game, card_id, inv_id="test_investigator"):
    inv = game.state.get_investigator(inv_id)
    inv.hand.append(card_id)
    return _emit(game, GameEvent.CARD_DRAWN, inv_id, extra={"card_id": card_id})


def _threat_cards(game, inv_id="test_investigator"):
    inv = game.state.get_investigator(inv_id)
    return [
        game.state.get_card_instance(iid).card_id
        for iid in inv.threat_area
        if game.state.get_card_instance(iid)
    ]


class TestCoverUp:
    def test_revelation_places_with_three_clues(self, game):
        _register(game, CoverUp)
        _draw(game, "cover_up")
        assert "cover_up" in _threat_cards(game)
        inst = next(
            game.state.get_card_instance(i)
            for i in game.state.get_investigator("test_investigator").threat_area
            if game.state.get_card_instance(i).card_id == "cover_up"
        )
        assert inst.uses["clues"] == 3

    def test_clue_discovery_redirected(self, game):
        impl = _register(game, CoverUp)
        _draw(game, "cover_up")
        inv = game.state.get_investigator("test_investigator")
        loc = game.state.locations["test_location"]

        ctx = _emit(
            game, GameEvent.CLUE_DISCOVERED,
            location_id="test_location", amount=1,
        )
        inv.clues += 0  # ctx 由引擎外手动触发，先模拟引擎的+1
        assert ctx.extra.get("cover_up_redirected") == 1
        inst = next(
            game.state.get_card_instance(i)
            for i in inv.threat_area
            if game.state.get_card_instance(i).card_id == "cover_up"
        )
        assert inst.uses["clues"] == 2
        assert loc.clues == 4  # 初始3 + cover_up 返还1（手动模拟，引擎实机会先-1）

    def test_game_end_penalty(self, game):
        impl = _register(game, CoverUp)
        _draw(game, "cover_up")
        assert impl.game_end_penalty(game.state, "test_investigator") is not None
        inv = game.state.get_investigator("test_investigator")
        assert inv.mental_trauma == 1

    def test_no_redirect_for_other_location(self, game):
        """卡面限定"在你的地点"：在其他地点发现线索不触发重定向。"""
        _register(game, CoverUp)
        _draw(game, "cover_up")
        inv = game.state.get_investigator("test_investigator")
        loc_b = make_location_data(id="loc_b", connections=["test_location"])
        game.register_card_data(loc_b)
        game.add_location("loc_b", loc_b)

        ctx = _emit(game, GameEvent.CLUE_DISCOVERED, location_id="loc_b", amount=1)
        assert "cover_up_redirected" not in ctx.extra
        inst = next(
            game.state.get_card_instance(i)
            for i in inv.threat_area
            if game.state.get_card_instance(i).card_id == "cover_up"
        )
        assert inst.uses["clues"] == 3  # 未弃线索


class TestHospitalDebts:
    def test_revelation_and_payment(self, game):
        impl = _register(game, HospitalDebts)
        _draw(game, "hospital_debts")
        assert "hospital_debts" in _threat_cards(game)

        inv = game.state.get_investigator("test_investigator")
        inv.resources = 3
        assert impl.activate(game.state, "test_investigator") is True
        assert inv.resources == 2
        assert impl.activate(game.state, "test_investigator") is True
        # 每轮限2次
        assert impl.activate(game.state, "test_investigator") is False
        # 新一轮重置
        _emit(game, GameEvent.ROUND_BEGINS)
        assert impl.activate(game.state, "test_investigator") is True

    def test_discarded_when_paid_off(self, game):
        impl = _register(game, HospitalDebts)
        _draw(game, "hospital_debts")
        inv = game.state.get_investigator("test_investigator")
        inv.resources = 10
        # 3轮，每轮付2个资源 = 6个
        for _ in range(3):
            assert impl.activate(game.state, "test_investigator") is True
            assert impl.activate(game.state, "test_investigator") is True
            _emit(game, GameEvent.ROUND_BEGINS)
        assert "hospital_debts" not in _threat_cards(game)
        assert "hospital_debts" in inv.discard
        assert impl.game_end_penalty(game.state, "test_investigator") is None

    def test_game_end_penalty_when_unpaid(self, game):
        impl = _register(game, HospitalDebts)
        _draw(game, "hospital_debts")
        assert impl.game_end_penalty(game.state, "test_investigator") is not None


class TestDarkMemory:
    def test_revelation_places_doom(self, game):
        _register(game, DarkMemory)
        doom_before = game.state.scenario.doom_on_agenda
        ctx = _draw(game, "dark_memory")
        assert game.state.scenario.doom_on_agenda == doom_before + 1
        assert ctx.extra.get("dark_memory_doom_placed") is True

    def test_played_from_hand_places_doom(self, game):
        """从手牌打出（事件，费用2）同样放置1个毁灭标记。"""
        _register(game, DarkMemory)
        _draw(game, "dark_memory")
        doom = game.state.scenario.doom_on_agenda
        _emit(game, GameEvent.CARD_PLAYED, extra={"card_id": "dark_memory"})
        assert game.state.scenario.doom_on_agenda == doom + 1

    def test_doom_placement_triggers_threshold_check(self, game):
        """放置毁灭后立即检查阈值，可能导致密谋推进。"""
        _register(game, DarkMemory)
        game.state.scenario.doom_threshold = 1
        idx = game.state.scenario.current_agenda_index
        _draw(game, "dark_memory")
        assert game.state.scenario.current_agenda_index == idx + 1
        assert game.state.scenario.doom_on_agenda == 0  # 推进后清空

    def test_turn_end_in_hand_causes_horror(self, game):
        _register(game, DarkMemory)
        _draw(game, "dark_memory")
        inv = game.state.get_investigator("test_investigator")
        assert "dark_memory" in inv.hand  # 留在手牌
        _emit(game, GameEvent.INVESTIGATOR_TURN_ENDS)
        assert inv.horror == 2
        # 卡面无弃牌语句：牌留在手牌，之后每回合结束重复触发
        assert "dark_memory" in inv.hand
        _emit(game, GameEvent.INVESTIGATOR_TURN_ENDS)
        assert inv.horror == 4
        assert "dark_memory" in inv.hand


class TestAbandonedAndAlone:
    def test_revelation(self, game):
        _register(game, AbandonedAndAlone)
        inv = game.state.get_investigator("test_investigator")
        inv.discard = ["card_x", "card_y"]
        _draw(game, "abandoned_and_alone")
        assert inv.horror == 2
        removed = game.state.scenario.vars["removed_from_game"]
        assert "card_x" in removed and "card_y" in removed
        assert inv.discard == ["abandoned_and_alone"]


class TestSmiteTheWicked:
    def test_revelation_spawns_enemy_at_farthest(self, game):
        impl = _register(game, SmiteTheWicked)
        # 构造地点连接：test_location - loc_b - loc_c
        loc_b = make_location_data(id="loc_b", connections=["test_location", "loc_c"])
        loc_c = make_location_data(id="loc_c", connections=["loc_b"])
        game.register_card_data(loc_b)
        game.register_card_data(loc_c)
        game.add_location("loc_b", loc_b)
        game.add_location("loc_c", loc_c)
        # 更新 test_location 的连接
        game.state.locations["test_location"].card_data.connections = ["loc_b"]

        enemy = make_enemy_data(id="ghoul")
        game.register_card_data(enemy)
        game.state.scenario.encounter_deck = ["some_treachery", "ghoul"]

        _draw(game, "smite_the_wicked_lv0")

        enemy_iid = game.state.scenario.vars.get("smite_the_wicked_enemy")
        assert enemy_iid is not None
        enemy_inst = game.state.get_card_instance(enemy_iid)
        assert enemy_inst.card_id == "ghoul"
        assert enemy_inst.attached_to == "loc_c"  # 最远地点
        assert "smite_the_wicked_lv0" in _threat_cards(game)
        # 敌人在场：游戏结束受创
        assert impl.game_end_penalty(game.state, "test_investigator") is not None

    def test_no_enemy_in_deck(self, game):
        _register(game, SmiteTheWicked)
        game.state.scenario.encounter_deck = ["treachery_a"]
        _draw(game, "smite_the_wicked_lv0")
        inv = game.state.get_investigator("test_investigator")
        assert "smite_the_wicked_lv0" in inv.discard
        assert "smite_the_wicked_enemy" not in game.state.scenario.vars


class TestRexsCurse:
    def test_revelation_to_threat_area(self, game):
        _register(game, RexsCurse)
        _draw(game, "rexs_curse_lv0")
        assert "rexs_curse_lv0" in _threat_cards(game)

    def test_redraw_causes_failure_and_shuffles_back(self, game):
        impl = _register(game, RexsCurse)
        bag = ChaosBag(tokens=[ChaosTokenType.MINUS_8])
        bag.seed(1)
        impl.bind_chaos_bag(bag)
        _draw(game, "rexs_curse_lv0")
        inv = game.state.get_investigator("test_investigator")
        deck_before = len(inv.deck)

        _emit(game, GameEvent.SKILL_TEST_BEGINS)
        ctx = _emit(
            game, GameEvent.SKILL_TEST_SUCCESSFUL,
            success=True, modified_skill=5, difficulty=2, amount=1,
        )
        assert ctx.success is False  # 5-1-8=-4 < 2 → 失败
        assert ctx.extra.get("rexs_curse_caused_failure") is True
        assert "rexs_curse_lv0" not in _threat_cards(game)
        assert len(inv.deck) == deck_before + 1

    def test_redraw_keeps_success_when_still_passing(self, game):
        impl = _register(game, RexsCurse)
        bag = ChaosBag(tokens=[ChaosTokenType.MINUS_1])
        bag.seed(1)
        impl.bind_chaos_bag(bag)
        _draw(game, "rexs_curse_lv0")

        _emit(game, GameEvent.SKILL_TEST_BEGINS)
        ctx = _emit(
            game, GameEvent.SKILL_TEST_SUCCESSFUL,
            success=True, modified_skill=6, difficulty=2, amount=1,
        )
        assert ctx.success is not False  # 6-1-1=4 >= 2 → 仍成功
        assert "rexs_curse_lv0" in _threat_cards(game)  # 仍在威胁区域


class TestSearchingForIzzie:
    def test_revelation_and_discard_on_investigate(self, game):
        _register(game, SearchingForIzzie)
        loc_b = make_location_data(id="loc_b", connections=["test_location"])
        game.register_card_data(loc_b)
        game.add_location("loc_b", loc_b)
        game.state.locations["test_location"].card_data.connections = ["loc_b"]

        _draw(game, "searching_for_izzie_lv0")
        assert "searching_for_izzie_lv0" in _threat_cards(game)
        assert game.state.scenario.vars["searching_for_izzie_location"] == "loc_b"

        inv = game.state.get_investigator("test_investigator")
        inv.clues = 0
        loc_b_state = game.state.locations["loc_b"]
        loc_b_state.clues = 1
        ctx = _emit(game, GameEvent.CLUE_DISCOVERED, location_id="loc_b", amount=1)
        assert ctx.extra.get("searching_for_izzie_discarded") is True
        assert "searching_for_izzie_lv0" not in _threat_cards(game)
        assert "searching_for_izzie_lv0" in inv.discard

    def test_game_end_penalty(self, game):
        impl = _register(game, SearchingForIzzie)
        _draw(game, "searching_for_izzie_lv0")
        assert impl.game_end_penalty(game.state, "test_investigator") is not None


class TestFinalRhapsody:
    def test_revelation_with_bound_bag(self, game):
        impl = _register(game, FinalRhapsody)
        bag = ChaosBag(tokens=[
            ChaosTokenType.SKULL, ChaosTokenType.AUTO_FAIL,
            ChaosTokenType.PLUS_1, ChaosTokenType.ZERO, ChaosTokenType.SKULL,
        ])
        bag.seed(42)
        impl.bind_chaos_bag(bag)
        inv = game.state.get_investigator("test_investigator")
        _draw(game, "final_rhapsody_lv0")
        drawn = None
        # 效果在 revelation 中直接结算
        assert inv.damage + inv.horror > 0  # 至少 skull/auto_fail 之一
        assert "final_rhapsody_lv0" in inv.discard

    def test_revelation_without_bag_is_noop(self, game):
        _register(game, FinalRhapsody)
        inv = game.state.get_investigator("test_investigator")
        _draw(game, "final_rhapsody_lv0")
        assert inv.damage == 0 and inv.horror == 0
        assert "final_rhapsody_lv0" in inv.discard


class TestWrackedByNightmares:
    def test_revelation_exhausts_assets(self, game):
        _register(game, WrackedByNightmares)
        inv = game.state.get_investigator("test_investigator")
        asset = CardInstance(
            instance_id="asset_1", card_id="some_asset",
            owner_id="test_investigator", controller_id="test_investigator",
        )
        game.state.cards_in_play["asset_1"] = asset
        inv.play_area.append("asset_1")

        _draw(game, "wracked_by_nightmares_lv0")
        assert asset.exhausted is True
        assert "wracked_by_nightmares_lv0" in _threat_cards(game)

    def test_assets_cannot_ready_and_discard(self, game):
        impl = _register(game, WrackedByNightmares)
        inv = game.state.get_investigator("test_investigator")
        asset = CardInstance(
            instance_id="asset_1", card_id="some_asset",
            owner_id="test_investigator", controller_id="test_investigator",
        )
        asset.exhausted = True
        game.state.cards_in_play["asset_1"] = asset
        inv.play_area.append("asset_1")
        _draw(game, "wracked_by_nightmares_lv0")

        # 模拟就绪事件 → 被重新横置
        asset.exhausted = False
        _emit(game, GameEvent.CARD_READIED, target="asset_1")
        assert asset.exhausted is True

        assert impl.activate_discard(game.state, "test_investigator") is True
        assert "wracked_by_nightmares_lv0" not in _threat_cards(game)


class TestChronophobia:
    def test_revelation_and_turn_end(self, game):
        impl = _register(game, Chronophobia)
        _draw(game, "chronophobia_lv0")
        inv = game.state.get_investigator("test_investigator")
        _emit(game, GameEvent.INVESTIGATOR_TURN_ENDS)
        assert inv.horror == 1
        assert impl.activate_discard(game.state, "test_investigator") is True
        _emit(game, GameEvent.INVESTIGATOR_TURN_ENDS)
        assert inv.horror == 1  # 丢弃后不再触发


class TestHypochondria:
    def test_horror_after_damage(self, game):
        impl = _register(game, Hypochondria)
        _draw(game, "hypochondria")
        inv = game.state.get_investigator("test_investigator")
        # 调查员受到伤害（DAMAGE_ASSIGNED）才触发；打敌人的 DAMAGE_DEALT 不触发
        _emit(game, GameEvent.DAMAGE_DEALT, amount=2)
        assert inv.horror == 0
        _emit(game, GameEvent.DAMAGE_ASSIGNED, amount=2)
        assert inv.horror == 1
        # 0伤害不触发
        _emit(game, GameEvent.DAMAGE_ASSIGNED, amount=0)
        assert inv.horror == 1
        assert impl.activate_discard(game.state, "test_investigator") is True


class TestIndebted:
    def test_revelation_reduces_resources(self, game):
        _register(game, Indebted)
        inv = game.state.get_investigator("test_investigator")
        inv.resources = 5
        _draw(game, "indebted_lv0")
        assert inv.resources == 3
        assert "indebted_lv0" in _threat_cards(game)


class TestInternalInjury:
    def test_turn_end_damage(self, game):
        impl = _register(game, InternalInjury)
        _draw(game, "internal_injury_lv0")
        inv = game.state.get_investigator("test_investigator")
        _emit(game, GameEvent.INVESTIGATOR_TURN_ENDS)
        assert inv.damage == 1
        assert impl.activate_discard(game.state, "test_investigator") is True


class TestSetupWeaknessSetAside:
    def test_opening_hand_weakness_set_aside_and_shuffled_back(self):
        """官方规则（附录III步骤8）：开局抽到的弱点搁置且不触发揭示，
        补抽替代；调度步骤完成后洗回牌库。"""
        from backend.engine.game import Game
        from backend.models.enums import CardType
        from backend.models.state import CardData
        from backend.tests.conftest import make_investigator_data, make_location_data

        g = Game("test_setup_weakness")
        inv_data = make_investigator_data()
        g.register_card_data(inv_data)
        loc_data = make_location_data()
        g.register_card_data(loc_data)
        g.register_card_data(CardData(
            id="cover_up", name="Cover Up", name_cn="掩盖真相",
            type=CardType.TREACHERY, subtype="weakness",
        ))
        deck = ["cover_up", "card_a", "card_b", "card_c", "card_d", "card_e"]
        g.add_investigator("p1", inv_data, deck=deck, starting_location="test_location")
        g.add_location("test_location", loc_data)
        g.setup()

        inv = g.state.get_investigator("p1")
        # 弱点不进手牌、不进威胁区、不触发揭示；补抽 card_e 凑满5张
        assert "cover_up" not in inv.hand
        assert inv.hand == ["card_a", "card_b", "card_c", "card_d", "card_e"]
        assert inv.threat_area == []
        assert g.state.scenario.vars["setup_set_aside"] == {"p1": ["cover_up"]}

        # 调度步骤完成 → 洗回牌库
        shuffled = g.shuffle_set_aside_into_decks()
        assert shuffled == ["cover_up"]
        assert "cover_up" in inv.deck
        assert "setup_set_aside" not in g.state.scenario.vars
