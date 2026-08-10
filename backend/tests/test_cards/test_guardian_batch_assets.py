"""Behavior tests for the guardian asset batch:
Ace of Swords (1), Agency Backup (5), Alice Luxley (0), Blessing of Isis (3),
Book of Psalms (0), Bruiser (3), Combat Training (3), Enchanted Armor (2),
Empty Vessel (4).
"""

import pytest

from backend.cards.guardian.ace_of_swords_lv1 import AceOfSwords
from backend.cards.guardian.agency_backup_lv5 import AgencyBackup
from backend.cards.guardian.alice_luxley_lv0 import AliceLuxley
from backend.cards.guardian.blessing_of_isis_lv3 import BlessingOfIsis
from backend.cards.guardian.book_of_psalms_lv0 import BookOfPsalms
from backend.cards.guardian.bruiser_lv3 import Bruiser
from backend.cards.guardian.combat_training_lv3 import CombatTrainingLv3
from backend.cards.guardian.empty_vessel_lv4 import EmptyVessel
from backend.cards.guardian.enchanted_armor_lv2 import EnchantedArmor
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import (
    Action, CardType, ChaosTokenType, GameEvent, PlayerClass, Skill, SlotType,
)
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_asset_data, make_enemy_data, make_investigator_data, make_location_data,
)


def _game(willpower=3, intellect=3, combat=3, agility=3, clues=0):
    g = Game("test")
    g.chaos_bag.seed(42)
    inv_data = make_investigator_data(
        willpower=willpower, intellect=intellect, combat=combat, agility=agility)
    g.register_card_data(inv_data)
    loc = make_location_data(clue_value=clues)
    g.register_card_data(loc)
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=clues)
    return g


def _equip(game, card_id, impl_cls, uses=None, traits=None, slots=None,
           health=None, sanity=None, owner="inv1"):
    if game.state.get_card_data(card_id) is None:
        game.register_card_data(make_asset_data(
            id=card_id, card_class=PlayerClass.GUARDIAN,
            slots=slots or [], uses=uses, traits=traits or [],
            health=health, sanity=sanity,
        ))
    game.card_registry.register_class(impl_cls)
    iid = game.state.next_instance_id()
    inst = CardInstance(
        instance_id=iid, card_id=card_id, owner_id=owner, controller_id=owner,
        uses=dict(uses or {}),
    )
    game.state.cards_in_play[iid] = inst
    game.state.get_investigator(owner).play_area.append(iid)
    impl = game.card_registry.activate_card(
        card_id, iid, game.event_bus, chaos_bag=game.chaos_bag)
    return impl, iid


def _enemy(game, fight=3, health=3, iid="enemy_1", engaged=True):
    data = make_enemy_data(fight=fight, health=health)
    game.register_card_data(data)
    inst = CardInstance(
        instance_id=iid, card_id="test_enemy",
        owner_id="scenario", controller_id="scenario",
    )
    game.state.cards_in_play[iid] = inst
    if engaged:
        game.state.get_investigator("inv1").threat_area.append(iid)
    else:
        game.state.get_location("test_location").enemies.append(iid)
    return inst


def _emit(game, event, **kwargs):
    ctx = EventContext(game_state=game.state, event=event, **kwargs)
    game.event_bus.emit(ctx)
    return ctx


class TestAceOfSwords:
    def test_put_into_play_from_opening_hand(self):
        """游戏开始时在起始手牌中：免费放置入场并占用塔罗槽。"""
        g = _game()
        g.card_registry.register_class(AceOfSwords)
        impl = g.card_registry.activate_card(
            "ace_of_swords_lv1", "ace_tmp", g.event_bus,
            chaos_bag=g.chaos_bag)
        inv = g.state.get_investigator("inv1")
        inv.hand = ["ace_of_swords_lv1"]
        iid = impl.put_into_play(g.state, "inv1")
        assert iid is not None
        assert "ace_of_swords_lv1" not in inv.hand
        assert iid in inv.play_area
        assert g.slot_managers["inv1"].get_cards_in_slot(SlotType.TAROT) == [iid]

    def test_combat_bonus_while_in_play(self):
        """在场时 +1 战斗（fight4 敌人，3+1=4 成功）。"""
        g = _game()
        _, iid = _equip(g, "ace_of_swords_lv1", AceOfSwords,
                        traits=["tarot"], slots=[SlotType.TAROT])
        enemy = _enemy(g, fight=4, health=5)
        g.chaos_bag.tokens = [ChaosTokenType.ZERO]
        inv = g.state.get_investigator("inv1")
        inv.actions_remaining = 3
        g.action_resolver.perform_action(
            "inv1", Action.FIGHT, enemy_instance_id="enemy_1")
        assert enemy.damage == 1

    def test_lazy_setup_on_round_begins(self):
        """ROUND_BEGINS 兜底：手牌中的宝剑王牌自动入场。"""
        g = _game()
        g.card_registry.register_class(AceOfSwords)
        g.card_registry.activate_card(
            "ace_of_swords_lv1", "ace_tmp", g.event_bus,
            chaos_bag=g.chaos_bag)
        inv = g.state.get_investigator("inv1")
        inv.hand = ["ace_of_swords_lv1"]
        _emit(g, GameEvent.ROUND_BEGINS)
        assert "ace_of_swords_lv1" not in inv.hand
        assert any(
            (g.state.get_card_instance(iid) or CardInstance("", "", "", "")).card_id
            == "ace_of_swords_lv1" for iid in inv.play_area)


class TestAgencyBackup:
    def test_punch_activation(self):
        """横置+自伤1：对同地点敌人造成1伤害。"""
        g = _game()
        impl, iid = _equip(g, "agency_backup_lv5", AgencyBackup,
                           traits=["ally", "agency"], slots=[SlotType.ALLY],
                           health=4, sanity=4)
        enemy = _enemy(g, health=5)
        assert impl.activate_punch(g.state, "inv1", "enemy_1") is True
        assert enemy.damage == 1
        inst = g.state.get_card_instance(iid)
        assert inst.exhausted is True
        assert inst.damage == 1

    def test_clue_activation(self):
        """横置+自恐1：发现同地点1条线索。"""
        g = _game(clues=1)
        impl, iid = _equip(g, "agency_backup_lv5", AgencyBackup,
                           traits=["ally", "agency"], slots=[SlotType.ALLY],
                           health=4, sanity=4)
        inv = g.state.get_investigator("inv1")
        assert impl.activate_clue(g.state, "inv1") is True
        assert inv.clues == 1
        assert g.state.get_location("test_location").clues == 0
        assert g.state.get_card_instance(iid).horror == 1

    def test_soaks_other_investigator_damage(self):
        """自动承担同地点其他调查员的伤害（至多剩余生命）。"""
        g = _game()
        inv_data2 = make_investigator_data(id="inv2", name="I2")
        g.register_card_data(inv_data2)
        g.add_investigator("inv2", inv_data2, starting_location="test_location")
        _, iid = _equip(g, "agency_backup_lv5", AgencyBackup,
                        traits=["ally", "agency"], slots=[SlotType.ALLY],
                        health=4, sanity=4)
        g.damage_engine.deal_damage("inv2", damage=3)
        inv2 = g.state.get_investigator("inv2")
        assert inv2.damage == 0
        assert g.state.get_card_instance(iid).damage == 3

    def test_self_damage_can_defeat_it(self):
        """自伤累积到生命上限时被击败离场。"""
        g = _game()
        impl, iid = _equip(g, "agency_backup_lv5", AgencyBackup,
                           traits=["ally", "agency"], slots=[SlotType.ALLY],
                           health=4, sanity=4)
        _enemy(g, health=20)
        inst = g.state.get_card_instance(iid)
        inst.damage = 3
        inv = g.state.get_investigator("inv1")
        assert impl.activate_punch(g.state, "inv1", "enemy_1") is True
        assert iid not in inv.play_area
        assert "agency_backup_lv5" in inv.discard


class TestAliceLuxley:
    def test_intellect_bonus_and_clue_trigger(self):
        """+1智力；发现线索后自动横置，对交战敌人造成1伤害。"""
        g = _game(clues=1)
        _, iid = _equip(g, "alice_luxley_lv0", AliceLuxley,
                        traits=["ally", "detective", "police"],
                        slots=[SlotType.ALLY], health=2, sanity=2)
        enemy = _enemy(g, health=5)
        g.chaos_bag.tokens = [ChaosTokenType.ZERO]
        inv = g.state.get_investigator("inv1")
        inv.actions_remaining = 3
        # 智力3+1=4 vs 掩盖2 → 成功发现线索 → 触发爱丽丝
        g.action_resolver.perform_action("inv1", Action.INVESTIGATE)
        assert inv.clues == 1
        assert enemy.damage == 1
        assert g.state.get_card_instance(iid).exhausted is True


class TestBlessingOfIsis:
    def _armed_isis(self, g):
        impl, iid = _equip(g, "blessing_of_isis_lv3", BlessingOfIsis,
                           traits=["ritual", "blessed"])
        assert impl.activate_arm(g.state, "inv1") is True
        return impl, iid

    def test_second_bless_converted(self):
        """武装后：同一检定第2个祝福标记被取消并视为远古印记。"""
        g = _game()
        impl, iid = self._armed_isis(g)
        _emit(g, GameEvent.SKILL_TEST_BEGINS, investigator_id="inv1")
        ctx1 = _emit(g, GameEvent.CHAOS_TOKEN_RESOLVED, investigator_id="inv1",
                     chaos_token=ChaosTokenType.BLESS, amount=2)
        assert ctx1.chaos_token == ChaosTokenType.BLESS  # 第1个不触发
        ctx2 = _emit(g, GameEvent.CHAOS_TOKEN_RESOLVED, investigator_id="inv1",
                     chaos_token=ChaosTokenType.BLESS, amount=2)
        assert ctx2.chaos_token == ChaosTokenType.ELDER_SIGN
        assert ctx2.amount == 0  # +2 祝福修正被取消
        assert g.state.get_card_instance(iid).exhausted is True

    def test_no_trigger_when_not_armed(self):
        """未武装：第2个祝福标记不触发。"""
        g = _game()
        _, iid = _equip(g, "blessing_of_isis_lv3", BlessingOfIsis,
                        traits=["ritual", "blessed"])
        _emit(g, GameEvent.SKILL_TEST_BEGINS, investigator_id="inv1")
        _emit(g, GameEvent.CHAOS_TOKEN_RESOLVED, investigator_id="inv1",
              chaos_token=ChaosTokenType.BLESS, amount=2)
        ctx2 = _emit(g, GameEvent.CHAOS_TOKEN_RESOLVED, investigator_id="inv1",
                     chaos_token=ChaosTokenType.BLESS, amount=2)
        assert ctx2.chaos_token == ChaosTokenType.BLESS
        assert g.state.get_card_instance(iid).exhausted is False


class TestBookOfPsalms:
    def test_heal_and_bless(self):
        """花1秘密：治愈1恐惧，袋中+2祝福（复数化 uses 键容错）。"""
        g = _game()
        impl, iid = _equip(g, "book_of_psalms_lv0", BookOfPsalms,
                           uses={"secretss": 4}, traits=["item", "tome", "blessed"],
                           slots=[SlotType.HAND])
        inv = g.state.get_investigator("inv1")
        inv.horror = 2
        before = g.chaos_bag.tokens.count(ChaosTokenType.BLESS)
        assert impl.activate(g.state, "inv1") is True
        assert inv.horror == 1
        assert g.state.get_card_instance(iid).uses["secretss"] == 3
        assert g.chaos_bag.tokens.count(ChaosTokenType.BLESS) == before + 2

    def test_no_horror_no_activation(self):
        """同地点无人有恐惧时不能启动。"""
        g = _game()
        impl, iid = _equip(g, "book_of_psalms_lv0", BookOfPsalms,
                           uses={"secrets": 4}, traits=["item", "tome", "blessed"],
                           slots=[SlotType.HAND])
        assert impl.activate(g.state, "inv1") is False
        assert g.state.get_card_instance(iid).uses["secrets"] == 4


class TestBruiser:
    def test_boost_on_weapon_test(self):
        """花卡上1资源：武器（firearm/melee）检定+1技能值。"""
        g = _game()
        impl, iid = _equip(g, "bruiser_lv3", Bruiser,
                           uses={"resourcess": 2}, traits=["talent"])
        # 一把无实现的 melee 武器作为检定来源
        g.register_card_data(make_asset_data(
            id="test_club", card_class=PlayerClass.GUARDIAN,
            traits=["item", "weapon", "melee"], slots=[SlotType.HAND]))
        club = CardInstance(
            instance_id="club_1", card_id="test_club",
            owner_id="inv1", controller_id="inv1")
        g.state.cards_in_play["club_1"] = club
        g.state.get_investigator("inv1").play_area.append("club_1")

        assert impl.spend(g.state, "inv1") is True
        assert g.state.get_card_instance(iid).uses["resourcess"] == 1
        g.chaos_bag.tokens = [ChaosTokenType.ZERO]
        result = g.skill_test_engine.run_test(
            "inv1", Skill.COMBAT, 4, source_instance_id="club_1")
        # 战斗3 + 打手1 = 4 vs 4 → 成功
        assert result.success is True

    def test_no_boost_on_non_weapon_test(self):
        """非武器/护甲检定：加值不适用。"""
        g = _game()
        impl, iid = _equip(g, "bruiser_lv3", Bruiser,
                           uses={"resources": 2}, traits=["talent"])
        assert impl.spend(g.state, "inv1") is True
        g.chaos_bag.tokens = [ChaosTokenType.ZERO]
        result = g.skill_test_engine.run_test("inv1", Skill.INTELLECT, 4)
        # 智力3，无加值 → 3 vs 4 失败
        assert result.success is False

    def test_replenish_each_round(self):
        """每轮开始：卡上资源补至2。"""
        g = _game()
        impl, iid = _equip(g, "bruiser_lv3", Bruiser,
                           uses={"resourcess": 0}, traits=["talent"])
        _emit(g, GameEvent.ROUND_BEGINS)
        assert g.state.get_card_instance(iid).uses["resourcess"] == 2


class TestCombatTrainingLv3:
    def test_passive_combat_bonus(self):
        """在场 +1 战斗：3+1=4 vs fight4 成功。"""
        g = _game()
        _equip(g, "combat_training_lv3", CombatTrainingLv3,
               traits=["talent", "composure"], health=3, sanity=1)
        enemy = _enemy(g, fight=4, health=5)
        g.chaos_bag.tokens = [ChaosTokenType.ZERO]
        inv = g.state.get_investigator("inv1")
        inv.actions_remaining = 3
        g.action_resolver.perform_action(
            "inv1", Action.FIGHT, enemy_instance_id="enemy_1")
        assert enemy.damage == 1

    def test_resource_boost_agility(self):
        """花1资源：敏捷检定+1。"""
        g = _game()
        impl, iid = _equip(g, "combat_training_lv3", CombatTrainingLv3,
                           traits=["talent", "composure"], health=3, sanity=1)
        inv = g.state.get_investigator("inv1")
        inv.resources = 2
        assert impl.spend(g.state, "inv1", Skill.AGILITY) is True
        g.chaos_bag.tokens = [ChaosTokenType.ZERO]
        result = g.skill_test_engine.run_test("inv1", Skill.AGILITY, 4)
        # 敏捷3+1=4 vs 4 → 成功
        assert result.success is True
        assert inv.resources == 1

    def test_soak_damage_and_horror(self):
        """非直接伤害/恐惧优先由本卡承担；达到上限被击败。"""
        g = _game()
        _, iid = _equip(g, "combat_training_lv3", CombatTrainingLv3,
                        traits=["talent", "composure"], health=3, sanity=1)
        inv = g.state.get_investigator("inv1")
        g.damage_engine.deal_damage("inv1", damage=2)
        assert inv.damage == 0
        assert g.state.get_card_instance(iid).damage == 2
        # 理智仅1：1点恐惧即击败
        g.damage_engine.deal_damage("inv1", horror=1)
        assert inv.horror == 0
        assert iid not in inv.play_area
        assert "combat_training_lv3" in inv.discard


class TestEnchantedArmor:
    def test_successful_test_keeps_damage(self):
        """承伤后意志检定成功：伤害留在护甲上。"""
        g = _game(willpower=3)
        impl, iid = _equip(g, "enchanted_armor_lv2", EnchantedArmor,
                           traits=["ritual", "armor"],
                           slots=[SlotType.BODY, SlotType.ARCANE],
                           health=3, sanity=3)
        g.chaos_bag.tokens = [ChaosTokenType.ZERO]
        inv = g.state.get_investigator("inv1")
        g.damage_engine.deal_damage("inv1", damage=2,
                                    damage_assignment={iid: 2})
        inst = g.state.get_card_instance(iid)
        assert inst is not None and inst.damage == 2
        assert inv.damage == 0
        assert iid in inv.play_area

    def test_failed_test_discards_and_reassigns(self):
        """承伤后意志检定失败：弃置护甲，伤害转移给拥有者。"""
        g = _game(willpower=3)
        impl, iid = _equip(g, "enchanted_armor_lv2", EnchantedArmor,
                           traits=["ritual", "armor"],
                           slots=[SlotType.BODY, SlotType.ARCANE],
                           health=3, sanity=3)
        g.chaos_bag.tokens = [ChaosTokenType.MINUS_4]  # 3-4<2 → 失败
        inv = g.state.get_investigator("inv1")
        g.damage_engine.deal_damage("inv1", damage=2,
                                    damage_assignment={iid: 2})
        assert iid not in inv.play_area
        assert "enchanted_armor_lv2" in inv.discard
        assert inv.damage == 2


class TestEmptyVessel:
    def test_charge_on_defeat_and_swap(self):
        """击败敌人放置充能；≥3充能交换为食愿项链并转移充能。"""
        g = _game()
        g.register_card_data(make_asset_data(
            id="wish_eater_lv0", card_class=PlayerClass.GUARDIAN,
            traits=["item", "relic", "blessed"], slots=[SlotType.ACCESSORY]))
        impl, iid = _equip(g, "empty_vessel_lv4", EmptyVessel,
                           uses={"chargess": 0},  # 数据复数化键容错
                           traits=["item", "relic", "blessed"],
                           slots=[SlotType.ACCESSORY])
        enemy = _enemy(g, health=5)
        for expected in (1, 2, 3):
            _emit(g, GameEvent.ENEMY_DEFEATED, investigator_id="inv1",
                  target="enemy_1", extra={"card_id": "test_enemy"})
            assert g.state.get_card_instance(iid).uses["chargess"] == expected

        inv = g.state.get_investigator("inv1")
        assert impl.activate_swap(g.state, "inv1") is True
        assert iid not in inv.play_area
        assert "empty_vessel_lv4" in g.state.scenario.vars["out_of_play"]
        wish_iids = [
            i for i in inv.play_area
            if g.state.get_card_instance(i).card_id == "wish_eater_lv0"
        ]
        assert len(wish_iids) == 1
        assert g.state.get_card_instance(wish_iids[0]).uses["charges"] == 3

    def test_swap_requires_3_charges(self):
        """不足3充能不能交换。"""
        g = _game()
        g.register_card_data(make_asset_data(
            id="wish_eater_lv0", card_class=PlayerClass.GUARDIAN,
            traits=["item", "relic", "blessed"], slots=[SlotType.ACCESSORY]))
        impl, iid = _equip(g, "empty_vessel_lv4", EmptyVessel,
                           uses={"charges": 2},
                           traits=["item", "relic", "blessed"],
                           slots=[SlotType.ACCESSORY])
        assert impl.activate_swap(g.state, "inv1") is False
