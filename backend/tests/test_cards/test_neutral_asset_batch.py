"""Tests for the neutral asset/event batch (Backpack .. Family Inheritance)."""

import pytest

from backend.cards.neutral.ace_of_rods_lv1 import AceOfRods
from backend.cards.neutral.anna_kaslow_lv4 import AnnaKaslow
from backend.cards.neutral.backpack_lv0 import Backpack
from backend.cards.neutral.becky_lv0 import Becky
from backend.cards.neutral.bounty_contracts_lv0 import BountyContracts
from backend.cards.neutral.call_for_backup_lv2 import CallForBackup
from backend.cards.neutral.dark_insight_lv0 import DarkInsight
from backend.cards.neutral.detectives_colt_1911s_lv0 import DetectivesColt1911s
from backend.cards.neutral.discipline_lv0 import Discipline
from backend.cards.neutral.dream_gate_lv0 import DreamGate
from backend.cards.neutral.family_inheritance_lv0 import FamilyInheritance
from backend.engine.event_bus import EventContext
from backend.models.enums import (
    Action, CardType, ChaosTokenType, GameEvent, PlayerClass, Skill, SlotType,
)
from backend.models.state import CardData, CardInstance
from backend.tests.conftest import (
    make_asset_data, make_enemy_data, make_location_data,
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


def _put_asset_in_play(game, card_id, instance_id="asset_1", uses=None,
                       card_data=None):
    if card_data is not None:
        game.register_card_data(card_data)
    inst = CardInstance(
        instance_id=instance_id, card_id=card_id,
        owner_id="test_investigator", controller_id="test_investigator",
        uses=dict(uses or {}),
    )
    game.state.cards_in_play[instance_id] = inst
    inv = game.state.get_investigator("test_investigator")
    inv.play_area.append(instance_id)
    return inst


def _spawn_engaged_enemy(game, enemy_id="enemy_1", card_id="test_enemy",
                         fight=3, health=3):
    game.register_card_data(make_enemy_data(id=card_id, fight=fight, health=health))
    enemy = CardInstance(
        instance_id=enemy_id, card_id=card_id,
        owner_id="scenario", controller_id="scenario",
    )
    game.state.cards_in_play[enemy_id] = enemy
    inv = game.state.get_investigator("test_investigator")
    inv.threat_area.append(enemy_id)
    return enemy


class TestBackpack:
    def test_attach_up_to_three_items(self, game):
        for i in range(4):
            game.register_card_data(make_asset_data(
                id=f"item_{i}", traits=["item"]))
        game.register_card_data(make_asset_data(
            id="spell_1", traits=["spell"]))
        inv = game.state.get_investigator("test_investigator")
        # 顶6张：item_0, spell_1, item_1, item_2, item_3(第5), item_x(无)
        inv.deck = ["item_0", "spell_1", "item_1", "item_2", "item_3"]

        inst = _put_asset_in_play(game, "backpack_lv0", instance_id="bp_1")
        impl = _register(game, Backpack, instance_id="bp_1")
        ctx = _emit(game, GameEvent.CARD_ENTERS_PLAY,
                    target="bp_1", extra={"card_id": "backpack_lv0"})
        attached = ctx.extra["backpack_attached"]
        assert attached == ["item_0", "item_1", "item_2"]  # 至多3张
        assert impl.attached_cards(game.state) == attached
        assert "spell_1" in inv.deck  # 非物品留在牌组
        assert "item_3" in inv.deck  # 超出3张留牌组

    def test_empty_backpack_discards_itself(self, game):
        game.register_card_data(make_asset_data(id="spell_1", traits=["spell"]))
        inv = game.state.get_investigator("test_investigator")
        inv.deck = ["spell_1"]
        _put_asset_in_play(game, "backpack_lv0", instance_id="bp_1")
        _register(game, Backpack, instance_id="bp_1")
        _emit(game, GameEvent.CARD_ENTERS_PLAY,
              target="bp_1", extra={"card_id": "backpack_lv0"})
        assert "bp_1" not in inv.play_area
        assert "backpack_lv0" in inv.discard

    def test_remove_attached_then_empty_discards(self, game):
        game.register_card_data(make_asset_data(id="item_0", traits=["item"]))
        inv = game.state.get_investigator("test_investigator")
        inv.deck = ["item_0"]
        _put_asset_in_play(game, "backpack_lv0", instance_id="bp_1")
        impl = _register(game, Backpack, instance_id="bp_1")
        _emit(game, GameEvent.CARD_ENTERS_PLAY,
              target="bp_1", extra={"card_id": "backpack_lv0"})
        assert impl.attached_cards(game.state) == ["item_0"]
        assert impl.remove_attached(game.state, "item_0") is True
        assert "bp_1" not in inv.play_area
        assert "backpack_lv0" in inv.discard


class TestBecky:
    def test_fight_bonus_and_ammo(self, game):
        gun_data = CardData(
            id="becky_lv0", name="Becky", name_cn="贝基",
            type=CardType.ASSET, card_class=PlayerClass.NEUTRAL, cost=2,
            traits=["item", "weapon", "firearm"], uses={"ammo": 2},
        )
        _put_asset_in_play(game, "becky_lv0", instance_id="becky_1",
                           uses={"ammo": 2}, card_data=gun_data)
        _register(game, Becky, instance_id="becky_1")
        enemy = _spawn_engaged_enemy(game, fight=5, health=6)
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]  # 战斗3+2=5 vs 5 → 命中

        game.action_resolver.perform_action(
            "test_investigator", Action.FIGHT,
            enemy_instance_id="enemy_1", weapon_instance_id="becky_1",
        )
        assert enemy.damage == 2  # 1基础 + 1加伤
        assert game.state.get_card_instance("becky_1").uses["ammo"] == 1

    def test_place_resource_as_ammo(self, game):
        _put_asset_in_play(game, "becky_lv0", instance_id="becky_1",
                           uses={"ammo": 1})
        impl = _register(game, Becky, instance_id="becky_1")
        assert impl.place_resource_as_ammo(game.state, "test_investigator") is True
        assert game.state.get_card_instance("becky_1").uses["ammo"] == 2


class TestBountyContracts:
    def test_place_bounties_capped_by_health(self, game):
        _put_asset_in_play(game, "bounty_contracts_lv0", instance_id="bc_1",
                           uses={"bountiess": 6})  # 数据键名笔误兼容
        impl = _register(game, BountyContracts, instance_id="bc_1")
        enemy = _spawn_engaged_enemy(game, health=3)
        enemy.damage = 1  # 剩余生命2 → 至多放2
        placed = impl.place_bounties(game.state, "enemy_1")
        assert placed == 2
        assert enemy.uses["bounties"] == 2
        assert game.state.get_card_instance("bc_1").uses["bounties"] == 4

    def test_defeat_collects_bounties(self, game):
        _put_asset_in_play(game, "bounty_contracts_lv0", instance_id="bc_1",
                           uses={"bounties": 3})
        _register(game, BountyContracts, instance_id="bc_1")
        enemy = _spawn_engaged_enemy(game, health=5)
        enemy.uses["bounties"] = 2
        inv = game.state.get_investigator("test_investigator")
        inv.resources = 0
        ctx = _emit(game, GameEvent.ENEMY_DEFEATED, target="enemy_1",
                    extra={"card_id": "test_enemy"})
        assert ctx.extra["bounty_contracts_collected"] == 2
        assert inv.resources == 2
        assert enemy.uses["bounties"] == 0

    def test_no_collection_for_other_defeater(self, game):
        _put_asset_in_play(game, "bounty_contracts_lv0", instance_id="bc_1",
                           uses={"bounties": 3})
        _register(game, BountyContracts, instance_id="bc_1")
        enemy = _spawn_engaged_enemy(game, health=5)
        enemy.uses["bounties"] = 2
        inv = game.state.get_investigator("test_investigator")
        inv.resources = 0
        ctx = _emit(game, GameEvent.ENEMY_DEFEATED, inv_id="someone_else",
                    target="enemy_1", extra={"card_id": "test_enemy"})
        assert "bounty_contracts_collected" not in ctx.extra
        assert inv.resources == 0


class TestCallForBackup:
    def test_guardian_and_seeker_effects(self, game):
        game.register_card_data(CardData(
            id="guard_card", name="G", name_cn="G", type=CardType.ASSET,
            card_class=PlayerClass.GUARDIAN,
        ))
        game.register_card_data(CardData(
            id="seeker_card", name="S", name_cn="S", type=CardType.ASSET,
            card_class=PlayerClass.SEEKER,
        ))
        _put_asset_in_play(game, "guard_card", instance_id="g_1")
        _put_asset_in_play(game, "seeker_card", instance_id="s_1")
        _register(game, CallForBackup)
        # 敌人在地点（未交战）
        enemy = _spawn_engaged_enemy(game, health=5)
        inv = game.state.get_investigator("test_investigator")
        inv.threat_area.remove("enemy_1")
        game.state.locations["test_location"].enemies.append("enemy_1")
        game.state.locations["test_location"].clues = 3

        ctx = _emit(game, GameEvent.CARD_PLAYED,
                    extra={"card_id": "call_for_backup_lv2"})
        applied = ctx.extra["call_for_backup_applied"]
        assert "guardian_damage" in applied
        assert "seeker_clue" in applied
        assert enemy.damage == 1
        assert game.state.locations["test_location"].clues == 2
        assert inv.clues == 1

    def test_survivor_heals_damage(self, game):
        game.register_card_data(CardData(
            id="surv_card", name="S", name_cn="S", type=CardType.ASSET,
            card_class=PlayerClass.SURVIVOR,
        ))
        _put_asset_in_play(game, "surv_card", instance_id="sv_1")
        _register(game, CallForBackup)
        inv = game.state.get_investigator("test_investigator")
        inv.damage = 2
        ctx = _emit(game, GameEvent.CARD_PLAYED,
                    extra={"card_id": "call_for_backup_lv2"})
        assert "survivor_heal_damage" in ctx.extra["call_for_backup_applied"]
        assert inv.damage == 1


class TestDarkInsight:
    def _weakness_data(self, game):
        game.register_card_data(CardData(
            id="wk_1", name="Weakness", name_cn="弱点",
            type=CardType.TREACHERY, card_class=PlayerClass.NEUTRAL,
            subtype="basic_weakness",
        ))

    def test_cancels_weakness_draw(self, game):
        self._weakness_data(game)
        game.register_card_data(CardData(
            id="dark_insight_lv0", name="Dark Insight", name_cn="黑暗洞察",
            type=CardType.EVENT, card_class=PlayerClass.NEUTRAL, cost=2,
        ))
        impl = _register(game, DarkInsight, instance_id="di_1")
        inv = game.state.get_investigator("test_investigator")
        inv.hand.append("dark_insight_lv0")
        inv.resources = 5
        inv.deck = []

        inv.hand.append("wk_1")
        ctx = _emit(game, GameEvent.CARD_DRAWN, extra={"card_id": "wk_1"})
        assert ctx.cancelled is True
        assert ctx.extra["dark_insight_cancelled"] == "wk_1"
        assert "wk_1" not in inv.hand
        assert "wk_1" in inv.deck  # 洗回牌组
        assert inv.resources == 3  # 支付2
        assert "dark_insight_lv0" in inv.discard

    def test_cancels_encounter_draw(self, game):
        game.register_card_data(CardData(
            id="dark_insight_lv0", name="Dark Insight", name_cn="黑暗洞察",
            type=CardType.EVENT, card_class=PlayerClass.NEUTRAL, cost=2,
        ))
        _register(game, DarkInsight, instance_id="di_1")
        inv = game.state.get_investigator("test_investigator")
        inv.hand.append("dark_insight_lv0")
        inv.resources = 5
        game.state.scenario.encounter_deck = []

        ctx = _emit(game, GameEvent.ENCOUNTER_CARD_DRAWN,
                    extra={"card_id": "enc_1"})
        assert ctx.cancelled is True
        assert "enc_1" in game.state.scenario.encounter_deck

    def test_no_cancel_without_resources(self, game):
        self._weakness_data(game)
        _register(game, DarkInsight, instance_id="di_1")
        inv = game.state.get_investigator("test_investigator")
        inv.hand.append("dark_insight_lv0")
        inv.resources = 1  # 不够支付2
        inv.hand.append("wk_1")
        ctx = _emit(game, GameEvent.CARD_DRAWN, extra={"card_id": "wk_1"})
        assert ctx.cancelled is False
        assert "wk_1" in inv.hand


class TestDetectivesColt:
    def _setup(self, game):
        gun_data = CardData(
            id="detectives_colt_1911s_lv0", name="Colt", name_cn="柯尔特",
            type=CardType.ASSET, card_class=PlayerClass.NEUTRAL, cost=4,
            traits=["item", "weapon", "firearm"], uses={"ammo": 4},
        )
        _put_asset_in_play(game, "detectives_colt_1911s_lv0",
                           instance_id="colt_1", uses={"ammo": 4},
                           card_data=gun_data)
        impl = _register(game, DetectivesColt1911s, instance_id="colt_1")
        return impl

    def test_fight_bonus_and_ammo(self, game):
        self._setup(game)
        enemy = _spawn_engaged_enemy(game, fight=4, health=6)
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]  # 3+1=4 vs 4 → 命中
        game.action_resolver.perform_action(
            "test_investigator", Action.FIGHT,
            enemy_instance_id="enemy_1", weapon_instance_id="colt_1",
        )
        assert enemy.damage == 2
        assert game.state.get_card_instance("colt_1").uses["ammo"] == 3

    def test_defeat_recycles_insight_event(self, game):
        self._setup(game)
        game.register_card_data(CardData(
            id="insight_evt", name="Insight", name_cn="洞察",
            type=CardType.EVENT, card_class=PlayerClass.SEEKER,
            traits=["insight"],
        ))
        inv = game.state.get_investigator("test_investigator")
        inv.discard.append("insight_evt")
        _spawn_engaged_enemy(game, fight=3, health=2)  # 1+1伤害恰好击败
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]
        game.action_resolver.perform_action(
            "test_investigator", Action.FIGHT,
            enemy_instance_id="enemy_1", weapon_instance_id="colt_1",
        )
        hunch = game.state.scenario.vars.get(
            "hunch_deck_test_investigator", [])
        assert "insight_evt" in hunch
        assert "insight_evt" not in inv.discard


class TestDiscipline:
    def _setup(self, game):
        _put_asset_in_play(game, "discipline_lv0", instance_id="disc_1")
        return _register(game, Discipline, instance_id="disc_1")

    def test_agility_bonus(self, game):
        self._setup(game)
        ctx = _emit(game, GameEvent.SKILL_VALUE_DETERMINED,
                    skill_type=Skill.AGILITY, amount=3)
        assert ctx.amount == 4

    def test_broken_removes_bonus_and_flip_back_rules(self, game):
        impl = self._setup(game)
        assert impl.activate(game.state, "test_investigator") is True
        ctx = _emit(game, GameEvent.SKILL_VALUE_DETERMINED,
                    skill_type=Skill.AGILITY, amount=3)
        assert ctx.amount == 3  # 破损面无加值
        # 当轮不能翻回
        assert impl.flip_back(game.state) is False
        # 下一轮可以翻回
        game.state.scenario.round_number += 1
        assert impl.flip_back(game.state) is True
        ctx = _emit(game, GameEvent.SKILL_VALUE_DETERMINED,
                    skill_type=Skill.AGILITY, amount=3)
        assert ctx.amount == 4


class TestDreamGate:
    def test_set_aside_at_investigation_phase_end(self, game):
        _register(game, DreamGate)
        game.register_card_data(make_location_data(id="dream_gate_lv0"))
        gate = game.add_location(
            "dream_gate_lv0", game.state.get_card_data("dream_gate_lv0"))
        gate.revealed = True
        game.state.locations["test_location"].revealed = True
        inv = game.state.get_investigator("test_investigator")
        inv.location_id = "dream_gate_lv0"

        ctx = _emit(game, GameEvent.INVESTIGATION_PHASE_ENDS)
        assert ctx.extra["dream_gate_set_aside"] is True
        assert "dream_gate_lv0" not in game.state.locations
        assert "dream_gate_lv0" in game.state.scenario.vars[
            "set_aside_locations"]
        assert inv.location_id == "test_location"  # 移动到已揭示地点


class TestFamilyInheritance:
    def _setup(self, game):
        _put_asset_in_play(game, "family_inheritance_lv0", instance_id="fi_1")
        return _register(game, FamilyInheritance, instance_id="fi_1")

    def test_turn_cycle(self, game):
        impl = self._setup(game)
        inst = game.state.get_card_instance("fi_1")
        inv = game.state.get_investigator("test_investigator")
        _emit(game, GameEvent.INVESTIGATOR_TURN_BEGINS)
        assert inst.uses["resources"] == 4
        # 像资源池一样花费
        assert impl.spend(game.state, "test_investigator", 3) is True
        assert inst.uses["resources"] == 1
        _emit(game, GameEvent.INVESTIGATOR_TURN_ENDS)
        assert inst.uses["resources"] == 0

    def test_activate_moves_to_pool(self, game):
        impl = self._setup(game)
        inst = game.state.get_card_instance("fi_1")
        inv = game.state.get_investigator("test_investigator")
        inv.resources = 0
        _emit(game, GameEvent.INVESTIGATOR_TURN_BEGINS)
        assert impl.activate(game.state, "test_investigator") is True
        assert inv.resources == 4
        assert inst.uses["resources"] == 0


class TestAceOfRods:
    def _setup(self, game):
        _put_asset_in_play(game, "ace_of_rods_lv1", instance_id="ace_1")
        return _register(game, AceOfRods, instance_id="ace_1")

    def test_activate_grants_action_and_boost(self, game):
        impl = self._setup(game)
        inv = game.state.get_investigator("test_investigator")
        inv.actions_remaining = 1
        assert impl.activate(game.state, "test_investigator") is True
        assert inv.actions_remaining == 2
        assert "ace_1" not in inv.play_area
        assert "ace_of_rods_lv1" in game.state.scenario.vars[
            "removed_from_game"]
        # 技能+2（本回合）
        ctx = _emit(game, GameEvent.SKILL_VALUE_DETERMINED,
                    skill_type=Skill.COMBAT, amount=3)
        assert ctx.amount == 5
        # 回合结束清除
        _emit(game, GameEvent.INVESTIGATOR_TURN_ENDS)
        ctx = _emit(game, GameEvent.SKILL_VALUE_DETERMINED,
                    skill_type=Skill.COMBAT, amount=3)
        assert ctx.amount == 3

    def test_put_into_play_at_game_begin(self, game):
        impl = _register(game, AceOfRods, instance_id="ace_x")
        inv = game.state.get_investigator("test_investigator")
        inv.hand.append("ace_of_rods_lv1")
        assert impl.put_into_play_at_game_begin(
            game.state, "test_investigator") is True
        assert "ace_of_rods_lv1" not in inv.hand
        assert any(
            game.state.get_card_instance(iid).card_id == "ace_of_rods_lv1"
            for iid in inv.play_area
        )


class TestAnnaKaslow:
    def test_enters_play_grants_slots_and_fetches_tarot(self, game):
        game.register_card_data(make_asset_data(
            id="tarot_1", traits=["tarot"]))
        inv = game.state.get_investigator("test_investigator")
        inv.deck = ["some_card", "tarot_1"]
        game.register_card_data(make_asset_data(id="some_card"))

        _put_asset_in_play(game, "anna_kaslow_lv4", instance_id="anna_1")
        _register(game, AnnaKaslow, instance_id="anna_1")
        ctx = _emit(game, GameEvent.CARD_ENTERS_PLAY,
                    target="anna_1", extra={"card_id": "anna_kaslow_lv4"})
        slot_mgr = game.slot_managers["test_investigator"]
        assert slot_mgr.bonus_slots.get(SlotType.TAROT) == 2
        assert ctx.extra["anna_kaslow_tarot"] == "tarot_1"
        assert any(
            game.state.get_card_instance(iid).card_id == "tarot_1"
            for iid in inv.play_area
        )
        assert "tarot_1" not in inv.deck

    def test_leaves_play_removes_slots(self, game):
        _put_asset_in_play(game, "anna_kaslow_lv4", instance_id="anna_1")
        _register(game, AnnaKaslow, instance_id="anna_1")
        _emit(game, GameEvent.CARD_ENTERS_PLAY,
              target="anna_1", extra={"card_id": "anna_kaslow_lv4"})
        _emit(game, GameEvent.CARD_LEAVES_PLAY,
              target="anna_1", extra={"card_id": "anna_kaslow_lv4"})
        slot_mgr = game.slot_managers["test_investigator"]
        assert slot_mgr.bonus_slots.get(SlotType.TAROT) is None
