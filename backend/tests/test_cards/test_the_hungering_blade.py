"""Tests for The Hungering Blade (Level 1). (06018)

[行动]攻击：每叠加1张嗜血+1战斗；+1伤害；攻击击败敌人后放置1贡品。
打出时额外费用：从绑定卡中查找3张嗜血洗入牌堆。
"""

import pytest
from backend.cards.guardian.the_hungering_blade_lv1 import TheHungeringBlade
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import (
    Action, ChaosTokenType, GameEvent, PlayerClass, SlotType,
)
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_asset_data, make_enemy_data, make_investigator_data,
    make_location_data,
)


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data(combat=4)
    g.register_card_data(inv_data)
    g.register_card_data(make_location_data())
    g.register_card_data(make_asset_data(
        id="the_hungering_blade_lv1", name="The Hungering Blade", cost=3,
        card_class=PlayerClass.GUARDIAN,
        slots=[SlotType.HAND], traits=["item", "weapon", "melee", "relic"],
        skill_icons={"combat": 1},
    ))
    g.register_card_data(make_enemy_data(
        id="rat", name="Rat", fight=3, health=5, damage=1, horror=0,
    ))

    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", g.state.get_card_data("test_location"))
    g.card_registry.register_class(TheHungeringBlade)
    return g


def _equip_blade(game):
    inv = game.state.get_investigator("inv1")
    inst_id = game.state.next_instance_id()
    game.state.cards_in_play[inst_id] = CardInstance(
        instance_id=inst_id, card_id="the_hungering_blade_lv1",
        owner_id="inv1", controller_id="inv1",
        slot_used=[SlotType.HAND],
    )
    inv.play_area.append(inst_id)
    game.card_registry.activate_card(
        "the_hungering_blade_lv1", inst_id, game.event_bus)
    return inst_id


def _spawn_engaged(game, instance_id="enemy_1"):
    game.state.cards_in_play[instance_id] = CardInstance(
        instance_id=instance_id, card_id="rat",
        owner_id="scenario", controller_id="scenario",
    )
    game.state.get_investigator("inv1").threat_area.append(instance_id)
    return game.state.cards_in_play[instance_id]


class TestTheHungeringBlade:
    def test_attack_deals_plus1_damage(self, game):
        """无叠加嗜血：攻击成功造成 1+1=2 伤害，无战斗加值。"""
        blade_id = _equip_blade(game)
        enemy = _spawn_engaged(game)
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]

        game.action_resolver.perform_action(
            "inv1", Action.FIGHT,
            enemy_instance_id="enemy_1", weapon_instance_id=blade_id,
        )
        assert enemy.damage == 2  # 基础1 + 卡面+1

    def test_bloodlust_stacks_combat(self, game):
        """每份叠加嗜血 +1战斗：4基础+2嗜血 vs 难度3，-3标记也成功。"""
        blade_id = _equip_blade(game)
        impl = game.card_registry.active_instances[blade_id]
        impl.attach_bloodlust(game.state, "inv1", "bloodlust_inst_1")
        impl.attach_bloodlust(game.state, "inv1", "bloodlust_inst_2")
        enemy = _spawn_engaged(game)
        game.chaos_bag.tokens = [ChaosTokenType.MINUS_3]

        game.action_resolver.perform_action(
            "inv1", Action.FIGHT,
            enemy_instance_id="enemy_1", weapon_instance_id=blade_id,
        )
        # 4 + 2(嗜血) - 3(标记) = 3 >= 3 → 成功，2伤害
        assert enemy.damage == 2

    def test_defeat_places_offering(self, game):
        """攻击击败敌人：从供应堆在刀上放1贡品（不扣玩家资源）。"""
        blade_id = _equip_blade(game)
        enemy = _spawn_engaged(game)
        enemy_data = game.state.get_card_data("rat")
        enemy_data.enemy_health = 2  # 2伤害即击败
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]
        inv = game.state.get_investigator("inv1")
        resources_before = inv.resources

        game.action_resolver.perform_action(
            "inv1", Action.FIGHT,
            enemy_instance_id="enemy_1", weapon_instance_id=blade_id,
        )

        blade = game.state.get_card_instance(blade_id)
        assert game.state.get_card_instance("enemy_1") is None  # 被击败
        assert blade.uses.get("offerings") == 1
        assert inv.resources == resources_before  # 贡品来自供应堆

    def test_no_offering_when_other_weapon_kills(self, game):
        """非本卡攻击（徒手）击败敌人：不放贡品。"""
        blade_id = _equip_blade(game)
        enemy = _spawn_engaged(game)
        game.state.get_card_data("rat").enemy_health = 1
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]

        game.action_resolver.perform_action(
            "inv1", Action.FIGHT,
            enemy_instance_id="enemy_1", weapon_instance_id=None,
        )
        blade = game.state.get_card_instance(blade_id)
        assert game.state.get_card_instance("enemy_1") is None
        assert blade.uses.get("offerings", 0) == 0

    def test_play_shuffle_bloodlust_from_bonded(self, game):
        """打出时：从绑定卡堆把3张嗜血洗入牌堆。"""
        game.state.scenario.vars["bonded_cards"] = {
            "inv1": ["bloodlust_lv0", "bloodlust_lv0", "bloodlust_lv0"],
        }
        blade_id = _equip_blade(game)
        inv = game.state.get_investigator("inv1")
        deck_before = len(inv.deck)

        ctx = EventContext(
            game_state=game.state, event=GameEvent.CARD_ENTERS_PLAY,
            investigator_id="inv1", target=blade_id,
            extra={"card_id": "the_hungering_blade_lv1"},
        )
        game.event_bus.emit(ctx)

        assert len(inv.deck) == deck_before + 3
        assert inv.deck.count("bloodlust_lv0") == 3
        assert game.state.scenario.vars["bonded_cards"]["inv1"] == []
