"""Tests for the neutral weakness batch (Accursed Fate .. Dream Parasite)."""

import pytest

from backend.cards.neutral.accursed_fate_lv0 import AccursedFate
from backend.cards.neutral.accursed_follower_lv0 import AccursedFollower
from backend.cards.neutral.arm_injury_lv0 import ArmInjury
from backend.cards.neutral.baron_samedi_lv0 import BaronSamedi
from backend.cards.neutral.bloodlust_lv0 import Bloodlust
from backend.cards.neutral.bought_in_blood_lv0 import BoughtInBlood
from backend.cards.neutral.burden_of_destiny_lv0 import BurdenOfDestiny
from backend.cards.neutral.buried_secrets_lv0 import BuriedSecrets
from backend.cards.neutral.call_of_the_unknown_lv0 import CallOfTheUnknown
from backend.cards.neutral.caught_red_handed_lv0 import CaughtRedHanded
from backend.cards.neutral.crisis_of_faith_lv0 import CrisisOfFaith
from backend.cards.neutral.dark_pact_lv0 import DarkPact
from backend.cards.neutral.day_of_reckoning_lv0 import DayOfReckoning
from backend.cards.neutral.detached_from_reality_lv0 import DetachedFromReality
from backend.cards.neutral.doomed_lv0 import Doomed
from backend.cards.neutral.dread_curse_lv0 import DreadCurse
from backend.cards.neutral.dream_parasite_lv0 import DreamParasite
from backend.engine.event_bus import EventContext
from backend.models.enums import (
    Action, CardType, ChaosTokenType, GameEvent, PlayerClass, Skill,
)
from backend.models.state import CardData, CardInstance
from backend.tests.conftest import (
    make_asset_data, make_enemy_data, make_investigator_data,
    make_location_data,
)


def _emit(game, event, inv_id="test_investigator", **kwargs):
    ctx = EventContext(
        game_state=game.state, event=event, investigator_id=inv_id, **kwargs
    )
    game.event_bus.emit(ctx)
    return ctx


def _register(game, impl_cls, instance_id="impl_1"):
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


class TestAccursedFate:
    def test_first_draw_horror_and_log(self, game):
        _register(game, AccursedFate)
        inv = game.state.get_investigator("test_investigator")
        _draw(game, "accursed_fate_lv0")
        assert inv.horror == 2
        assert "the hour is nigh" in game.state.scenario.vars["campaign_log"]
        assert "accursed_fate_lv0" in inv.discard

    def test_second_draw_places_bell_tolls_on_deck_bottom(self, game):
        _register(game, AccursedFate)
        game.state.scenario.vars["campaign_log"] = ["the hour is nigh"]
        inv = game.state.get_investigator("test_investigator")
        inv.deck = ["some_card"]
        ctx = _draw(game, "accursed_fate_lv0")
        assert ctx.extra["accursed_fate_upgraded"] is True
        assert "accursed_fate_lv0" in game.state.scenario.vars["removed_from_game"]
        assert inv.deck[-1] == "the_bell_tolls_lv0"
        assert "accursed_fate_lv0" not in inv.discard


class TestDoomed:
    def test_first_draw(self, game):
        _register(game, Doomed)
        inv = game.state.get_investigator("test_investigator")
        _draw(game, "doomed_lv0")
        assert inv.horror == 1
        assert "doom approaches" in game.state.scenario.vars["campaign_log"]
        assert "doomed_lv0" in inv.discard

    def test_repeat_draw_upgrades(self, game):
        _register(game, Doomed)
        game.state.scenario.vars["campaign_log"] = ["doom approaches"]
        inv = game.state.get_investigator("test_investigator")
        inv.deck = []
        _draw(game, "doomed_lv0")
        assert inv.deck[-1] == "accursed_fate_lv0"
        assert "doomed_lv0" in game.state.scenario.vars["removed_from_game"]


class TestDreadCurse:
    def test_adds_five_curse_tokens(self, game):
        impl = _register(game, DreadCurse)
        impl.bind_chaos_bag(game.chaos_bag)
        before = game.chaos_bag.tokens.count(ChaosTokenType.CURSE)
        ctx = _draw(game, "dread_curse_lv0")
        assert ctx.extra["dread_curse_added"] == 5
        assert game.chaos_bag.tokens.count(ChaosTokenType.CURSE) == before + 5


class TestCrisisOfFaith:
    def test_bless_replaced_by_curse(self, game):
        impl = _register(game, CrisisOfFaith)
        game.chaos_bag.tokens = [
            ChaosTokenType.BLESS, ChaosTokenType.BLESS, ChaosTokenType.ZERO,
        ]
        impl.bind_chaos_bag(game.chaos_bag)
        ctx = _draw(game, "crisis_of_faith_lv0")
        assert ctx.extra["crisis_of_faith_replaced"] == 2
        assert ChaosTokenType.BLESS not in game.chaos_bag.tokens
        assert game.chaos_bag.tokens.count(ChaosTokenType.CURSE) == 2
        inv = game.state.get_investigator("test_investigator")
        assert inv.horror == 0


class TestBoughtInBlood:
    def test_discards_ally_in_play(self, game):
        _register(game, BoughtInBlood)
        game.register_card_data(make_asset_data(id="ally_1", traits=["ally"]))
        inst = CardInstance(
            instance_id="ally_inst", card_id="ally_1",
            owner_id="test_investigator", controller_id="test_investigator",
        )
        game.state.cards_in_play["ally_inst"] = inst
        inv = game.state.get_investigator("test_investigator")
        inv.play_area.append("ally_inst")

        ctx = _draw(game, "bought_in_blood_lv0")
        assert ctx.extra["bought_in_blood_discarded_play"] == "ally_inst"
        assert "ally_inst" not in inv.play_area
        assert "ally_1" in inv.discard
        assert "bought_in_blood_lv0" in inv.discard

    def test_no_allies_shuffles_back(self, game):
        _register(game, BoughtInBlood)
        inv = game.state.get_investigator("test_investigator")
        inv.deck = []
        ctx = _draw(game, "bought_in_blood_lv0")
        assert ctx.extra["bought_in_blood_shuffled_back"] is True
        assert "bought_in_blood_lv0" in inv.deck
        assert "bought_in_blood_lv0" not in inv.discard

    def test_discards_allies_from_hand(self, game):
        _register(game, BoughtInBlood)
        game.register_card_data(make_asset_data(id="ally_h", traits=["ally"]))
        inv = game.state.get_investigator("test_investigator")
        inv.hand.append("ally_h")
        ctx = _draw(game, "bought_in_blood_lv0")
        assert ctx.extra["bought_in_blood_discarded_hand"] == ["ally_h"]
        assert "ally_h" in inv.discard
        assert "bought_in_blood_lv0" in inv.discard


class TestDayOfReckoning:
    def test_attach_and_seal_elder_sign(self, game):
        impl = _register(game, DayOfReckoning)
        impl.bind_chaos_bag(game.chaos_bag)
        game.state.scenario.agenda_deck = ["agenda_1"]
        assert ChaosTokenType.ELDER_SIGN in game.chaos_bag.tokens
        ctx = _draw(game, "day_of_reckoning_lv0")
        record = game.state.scenario.vars["day_of_reckoning"]
        assert record["agenda"] == "agenda_1"
        assert record["sealed"] == "elder_sign"
        assert ChaosTokenType.ELDER_SIGN not in game.chaos_bag.tokens
        assert ChaosTokenType.ELDER_SIGN in game.chaos_bag.sealed
        assert "day_of_reckoning_lv0" not in game.state.get_investigator(
            "test_investigator").hand


class TestAccursedFollower:
    def test_adds_curse_at_enemy_phase_end(self, game):
        game.register_card_data(make_enemy_data(
            id="accursed_follower_lv0", fight=2, health=2, evade=2,
            keywords=["aloof"],
        ))
        inst = CardInstance(
            instance_id="follower_1", card_id="accursed_follower_lv0",
            owner_id="test_investigator", controller_id="scenario",
        )
        game.state.cards_in_play["follower_1"] = inst
        game.state.locations["test_location"].enemies.append("follower_1")

        impl = _register(game, AccursedFollower, instance_id="follower_1")
        impl.bind_chaos_bag(game.chaos_bag)
        before = game.chaos_bag.tokens.count(ChaosTokenType.CURSE)
        _emit(game, GameEvent.ENEMY_PHASE_ENDS)
        assert game.chaos_bag.tokens.count(ChaosTokenType.CURSE) == before + 1

    def test_no_curse_when_defeated(self, game):
        impl = _register(game, AccursedFollower, instance_id="follower_x")
        impl.bind_chaos_bag(game.chaos_bag)
        before = game.chaos_bag.tokens.count(ChaosTokenType.CURSE)
        _emit(game, GameEvent.ENEMY_PHASE_ENDS)
        assert game.chaos_bag.tokens.count(ChaosTokenType.CURSE) == before


class TestArmInjury:
    def test_revelation_enters_threat_area(self, game):
        _register(game, ArmInjury)
        _draw(game, "arm_injury_lv0")
        assert "arm_injury_lv0" in _threat_cards(game)

    def test_blocks_fight_after_fight(self, game):
        impl = _register(game, ArmInjury)
        _draw(game, "arm_injury_lv0")
        assert impl.can_take_action(
            game.state, "test_investigator", Action.FIGHT) is True
        _emit(game, GameEvent.ACTION_PERFORMED, action=Action.FIGHT)
        assert impl.can_take_action(
            game.state, "test_investigator", Action.FIGHT) is False
        assert impl.can_take_action(
            game.state, "test_investigator", Action.MOVE) is True
        # 回合开始重置
        _emit(game, GameEvent.INVESTIGATOR_TURN_BEGINS)
        assert impl.can_take_action(
            game.state, "test_investigator", Action.FIGHT) is True

    def test_heal_discards(self, game):
        impl = _register(game, ArmInjury)
        _draw(game, "arm_injury_lv0")
        assert impl.heal(game.state, "test_investigator") is True
        assert "arm_injury_lv0" not in _threat_cards(game)
        inv = game.state.get_investigator("test_investigator")
        assert "arm_injury_lv0" in inv.discard


class TestBaronSamedi:
    def _put_in_play(self, game):
        _register(game, BaronSamedi)
        _draw(game, "baron_samedi_lv0")
        inv = game.state.get_investigator("test_investigator")
        inst_id = next(
            iid for iid in inv.play_area
            if game.state.get_card_instance(iid).card_id == "baron_samedi_lv0"
        )
        return game.state.get_card_instance(inst_id)

    def test_revelation_enters_play(self, game):
        baron = self._put_in_play(game)
        assert baron is not None
        assert baron.doom == 0

    def test_extra_damage_at_his_location(self, game):
        self._put_in_play(game)
        inv = game.state.get_investigator("test_investigator")
        ctx = _emit(game, GameEvent.DAMAGE_ASSIGNED, amount=2)
        assert ctx.extra["baron_samedi_extra_damage"] is True
        assert inv.damage == 1  # 额外1点直接放置（原2点由引擎另行结算）

    def test_no_extra_damage_elsewhere(self, game):
        self._put_in_play(game)
        loc_b = make_location_data(id="loc_b")
        game.register_card_data(loc_b)
        game.add_location("loc_b", loc_b)
        # 第二名调查员在另一地点承伤：不在男爵所在地点，不触发
        other_data = make_investigator_data(id="other_inv")
        game.register_card_data(other_data)
        game.add_investigator("other_inv", other_data, starting_location="loc_b")
        other = game.state.get_investigator("other_inv")
        ctx = _emit(game, GameEvent.DAMAGE_ASSIGNED, inv_id="other_inv", amount=2)
        assert "baron_samedi_extra_damage" not in ctx.extra
        assert other.damage == 0

    def test_three_doom_discards(self, game):
        impl = BaronSamedi("any")
        impl.register(game.event_bus, "any")
        baron = self._put_in_play(game)
        inv = game.state.get_investigator("test_investigator")
        for _ in range(2):
            assert impl.activate_place_doom(game.state, "test_investigator") is True
            baron.exhausted = False  # 测试直接重置（正常经补给阶段）
        assert impl.can_leave_play(game.state) is False
        assert impl.activate_place_doom(game.state, "test_investigator") is True
        assert baron.doom == 3
        assert baron.instance_id not in inv.play_area
        assert "baron_samedi_lv0" in inv.discard


class TestBloodlust:
    def _blade(self, game, offerings=2):
        game.register_card_data(make_asset_data(
            id="the_hungering_blade_lv1", traits=["item", "weapon"]))
        blade = CardInstance(
            instance_id="blade_1", card_id="the_hungering_blade_lv1",
            owner_id="test_investigator", controller_id="test_investigator",
            uses={"offerings": offerings},
        )
        game.state.cards_in_play["blade_1"] = blade
        inv = game.state.get_investigator("test_investigator")
        inv.play_area.append("blade_1")
        return blade

    def test_attach_removes_offerings(self, game):
        _register(game, Bloodlust)
        blade = self._blade(game, offerings=2)
        ctx = _draw(game, "bloodlust_lv0")
        assert blade.uses["offerings"] == 0
        attached = next(
            c for c in game.state.cards_in_play.values()
            if c.card_id == "bloodlust_lv0"
        )
        assert attached.attached_to == "blade_1"
        assert ctx.extra["bloodlust_attached"] == "blade_1"

    def test_cannot_pay_takes_horror_and_shuffles(self, game):
        _register(game, Bloodlust)
        self._blade(game, offerings=1)
        inv = game.state.get_investigator("test_investigator")
        inv.deck = []
        ctx = _draw(game, "bloodlust_lv0")
        assert ctx.extra["bloodlust_shuffled_back"] is True
        assert inv.horror == 1
        assert "bloodlust_lv0" in inv.deck

    def test_bonus_damage_shuffles_into_deck(self, game):
        impl = _register(game, Bloodlust)
        blade = self._blade(game, offerings=2)
        _draw(game, "bloodlust_lv0")
        bloodlust_inst = next(
            c for c in game.state.cards_in_play.values()
            if c.card_id == "bloodlust_lv0"
        )
        # 以嗜血之刃攻击：DAMAGE_DEALT 时自动洗回并+1伤害
        inv = game.state.get_investigator("test_investigator")
        inv.deck = []
        ctx = _emit(
            game, GameEvent.DAMAGE_DEALT, source="blade_1",
            target="enemy_1", amount=1,
        )
        assert ctx.amount == 2  # +1伤害
        assert "bloodlust_lv0" in inv.deck
        assert bloodlust_inst.instance_id not in game.state.cards_in_play


class TestBurdenOfDestiny:
    def test_flips_discipline(self, game):
        _register(game, BurdenOfDestiny)
        game.register_card_data(make_asset_data(id="discipline_lv0"))
        inst = CardInstance(
            instance_id="disc_1", card_id="discipline_lv0",
            owner_id="test_investigator", controller_id="test_investigator",
        )
        game.state.cards_in_play["disc_1"] = inst
        inv = game.state.get_investigator("test_investigator")
        inv.play_area.append("disc_1")
        ctx = _draw(game, "burden_of_destiny_lv0")
        assert ctx.extra["burden_of_destiny_flipped"] == "disc_1"
        assert "discipline_broken_disc_1" in game.state.scenario.vars
        assert inv.damage == 0 and inv.horror == 0

    def test_no_discipline_takes_damage_and_horror(self, game):
        _register(game, BurdenOfDestiny)
        inv = game.state.get_investigator("test_investigator")
        ctx = _draw(game, "burden_of_destiny_lv0")
        assert ctx.extra["burden_of_destiny_suffered"] is True
        assert inv.damage == 1 and inv.horror == 1


class TestBuriedSecrets:
    def test_revelation_and_move_block(self, game):
        impl = _register(game, BuriedSecrets)
        _draw(game, "buried_secrets_lv0")
        assert "buried_secrets_lv0" in _threat_cards(game)
        assert impl.blocks_move(game.state, "test_investigator") is True

    def test_successful_investigate_discards_without_clues(self, game):
        impl = _register(game, BuriedSecrets)
        _draw(game, "buried_secrets_lv0")
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]  # 智力3 vs 隐藏值2 → 成功
        loc = game.state.locations["test_location"]
        assert loc.clues == 3
        assert impl.activate(game, "test_investigator") is True
        inv = game.state.get_investigator("test_investigator")
        assert "buried_secrets_lv0" in inv.discard
        assert "buried_secrets_lv0" not in _threat_cards(game)
        assert loc.clues == 3  # 未发现线索
        assert inv.clues == 0

    def test_failed_investigate_can_shuffle_with_horror(self, game):
        impl = _register(game, BuriedSecrets)
        _draw(game, "buried_secrets_lv0")
        game.chaos_bag.tokens = [ChaosTokenType.MINUS_8]  # 必败
        inv = game.state.get_investigator("test_investigator")
        inv.deck = []
        assert impl.activate(game, "test_investigator") is True
        assert impl._failed is True
        assert impl.take_horror_to_shuffle(game.state, "test_investigator") is True
        assert inv.horror == 2
        assert "buried_secrets_lv0" in inv.deck
        assert "buried_secrets_lv0" not in _threat_cards(game)


class TestCallOfTheUnknown:
    def _setup_two_locations(self, game):
        loc_b = make_location_data(id="loc_b")
        game.register_card_data(loc_b)
        game.add_location("loc_b", loc_b)

    def test_turn_end_without_investigating(self, game):
        _register(game, CallOfTheUnknown)
        self._setup_two_locations(game)
        _draw(game, "call_of_the_unknown_lv0")
        inv = game.state.get_investigator("test_investigator")
        inv.deck = []
        _emit(game, GameEvent.INVESTIGATOR_TURN_BEGINS)
        ctx = _emit(game, GameEvent.INVESTIGATOR_TURN_ENDS)
        assert ctx.extra["call_of_the_unknown_shuffled_back"] is True
        assert inv.horror == 2
        assert "call_of_the_unknown_lv0" in inv.deck
        assert "call_of_the_unknown_lv0" not in _threat_cards(game)

    def test_successful_investigation_satisfies(self, game):
        _register(game, CallOfTheUnknown)
        self._setup_two_locations(game)
        _draw(game, "call_of_the_unknown_lv0")
        inv = game.state.get_investigator("test_investigator")
        _emit(game, GameEvent.INVESTIGATOR_TURN_BEGINS)
        # 移动到所选地点并成功完成一次智力检定
        inv.location_id = "loc_b"
        _emit(game, GameEvent.SKILL_TEST_SUCCESSFUL,
              skill_type=Skill.INTELLECT, success=True)
        ctx = _emit(game, GameEvent.INVESTIGATOR_TURN_ENDS)
        assert ctx.extra["call_of_the_unknown_satisfied"] is True
        assert inv.horror == 0
        assert "call_of_the_unknown_lv0" in _threat_cards(game)  # 留在威胁区


class TestCaughtRedHanded:
    def _setup(self, game, hunter=True, exhausted=True):
        loc_b = make_location_data(id="loc_b", connections=["test_location"])
        game.register_card_data(loc_b)
        game.add_location("loc_b", loc_b)
        game.state.locations["test_location"].card_data.connections.append("loc_b")
        keywords = ["hunter"] if hunter else []
        game.register_card_data(make_enemy_data(id="hunter_1", keywords=keywords))
        enemy = CardInstance(
            instance_id="enemy_h", card_id="hunter_1",
            owner_id="scenario", controller_id="scenario",
            exhausted=exhausted,
        )
        game.state.cards_in_play["enemy_h"] = enemy
        game.state.locations["loc_b"].enemies.append("enemy_h")
        return enemy

    def test_hunter_moves_and_readies(self, game):
        _register(game, CaughtRedHanded)
        enemy = self._setup(game, hunter=True, exhausted=True)
        inv = game.state.get_investigator("test_investigator")
        ctx = _draw(game, "caught_red_handed_lv0")
        assert ctx.extra["caught_red_handed"]["moved"] == 1
        assert enemy.exhausted is False  # 被准备
        assert "enemy_h" in game.state.locations["test_location"].enemies
        assert "enemy_h" not in game.state.locations["loc_b"].enemies
        assert "caught_red_handed_lv0" in inv.discard

    def test_no_movement_shuffles_back(self, game):
        _register(game, CaughtRedHanded)
        self._setup(game, hunter=False)  # 非猎手不移动
        inv = game.state.get_investigator("test_investigator")
        inv.deck = []
        ctx = _draw(game, "caught_red_handed_lv0")
        assert ctx.extra["caught_red_handed"]["moved"] == 0
        assert ctx.extra["caught_red_handed"]["shuffled_back"] is True
        assert "caught_red_handed_lv0" in inv.deck


class TestDarkPact:
    def test_play_deals_2_damage(self, game):
        _register(game, DarkPact)
        inv = game.state.get_investigator("test_investigator")
        _emit(game, GameEvent.CARD_PLAYED, extra={"card_id": "dark_pact_lv0"})
        assert inv.damage == 2

    def test_game_end_penalty(self, game):
        impl = _register(game, DarkPact)
        inv = game.state.get_investigator("test_investigator")
        inv.hand.append("dark_pact_lv0")
        msg = impl.game_end_penalty(game.state, "test_investigator")
        assert msg is not None
        assert "dark_pact_lv0" not in inv.hand
        assert "dark_pact_lv0" in game.state.scenario.vars["removed_from_game"]
        assert "the_price_of_failure_lv0" in inv.deck
        # 已结算过则不再触发
        assert impl.game_end_penalty(game.state, "test_investigator") is None


class TestDetachedFromReality:
    def test_gate_enters_and_moves(self, game):
        _register(game, DetachedFromReality)
        game.register_card_data(make_location_data(id="dream_gate_lv0"))
        # 交战敌人
        game.register_card_data(make_enemy_data(id="eng_1"))
        enemy = CardInstance(
            instance_id="enemy_e", card_id="eng_1",
            owner_id="scenario", controller_id="scenario",
        )
        game.state.cards_in_play["enemy_e"] = enemy
        inv = game.state.get_investigator("test_investigator")
        inv.threat_area.append("enemy_e")

        ctx = _draw(game, "detached_from_reality_lv0")
        assert ctx.extra["detached_from_reality_entered"] is True
        assert "dream_gate_lv0" in game.state.locations
        assert inv.location_id == "dream_gate_lv0"
        assert "enemy_e" not in inv.threat_area  # 解除交战
        assert "enemy_e" in game.state.locations["test_location"].enemies

    def test_existing_gate_flips(self, game):
        _register(game, DetachedFromReality)
        game.register_card_data(make_location_data(id="dream_gate_lv0"))
        game.add_location("dream_gate_lv0",
                          game.state.get_card_data("dream_gate_lv0"))
        ctx = _draw(game, "detached_from_reality_lv0")
        assert ctx.extra["detached_from_reality_flipped"] is True
        assert game.state.scenario.vars["dream_gate_flipped"] is True
        inv = game.state.get_investigator("test_investigator")
        assert inv.location_id == "dream_gate_lv0"


class TestDreamParasite:
    def test_icons_subtract_and_failure_penalty(self, game):
        game.register_card_data(CardData(
            id="dream_parasite_lv0", name="Dream Parasite", name_cn="梦寄生",
            type=CardType.SKILL, card_class=PlayerClass.NEUTRAL,
            subtype="weakness", skill_icons={"wild": 2},
        ))
        game.card_registry.register_class(DreamParasite)
        inv = game.state.get_investigator("test_investigator")
        inv.hand.append("dream_parasite_lv0")
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]

        result = game.skill_test_engine.run_test(
            investigator_id="test_investigator",
            skill_type=Skill.WILLPOWER,
            difficulty=3,  # 意志3 - 2图标 = 1 < 3 → 失败
            committed_card_ids=["dream_parasite_lv0"],
        )
        assert result.committed_icons == -2  # 图标反转
        assert result.success is False
        assert inv.damage == 1 and inv.horror == 1
