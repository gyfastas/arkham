"""Tests for Aquinnah (Level 1 and Level 3)."""

import pytest
from backend.cards.survivor.aquinnah_lv1 import AquinnahLv1
from backend.cards.survivor.aquinnah_lv3 import AquinnahLv3
from backend.models.enums import PlayerClass, SlotType
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_enemy_data, make_investigator_data, make_asset_data, make_location_data,
)
from backend.engine.game import Game


@pytest.fixture
def game():
    g = Game("test")
    inv_data = make_investigator_data()
    g.register_card_data(inv_data)
    loc = make_location_data()
    g.register_card_data(loc)

    aq1_data = make_asset_data(
        id="aquinnah_lv1", name="Aquinnah", cost=5,
        card_class=PlayerClass.SURVIVOR,
        slots=[SlotType.ALLY], health=1, sanity=4,
        traits=["ally"],
    )
    g.register_card_data(aq1_data)

    aq3_data = make_asset_data(
        id="aquinnah_lv3", name="Aquinnah", cost=4,
        card_class=PlayerClass.SURVIVOR,
        slots=[SlotType.ALLY], health=1, sanity=4,
        traits=["ally"],
    )
    g.register_card_data(aq3_data)

    g.register_card_data(make_enemy_data(
        id="ghoul", fight=3, health=3, evade=3, damage=2, horror=1))

    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)
    g.card_registry.register_class(AquinnahLv1)
    g.card_registry.register_class(AquinnahLv3)
    return g


def _put_aquinnah_in_play(game, card_id="aquinnah_lv1"):
    inv = game.state.get_investigator("inv1")
    iid = game.state.next_instance_id()
    game.state.cards_in_play[iid] = CardInstance(
        instance_id=iid, card_id=card_id,
        owner_id="inv1", controller_id="inv1", slot_used=[SlotType.ALLY],
    )
    inv.play_area.append(iid)
    game.card_registry.activate_card(card_id, iid, game.event_bus)
    return iid


def _spawn_enemy(game, instance_id, card_id="ghoul", engaged=True):
    game.state.cards_in_play[instance_id] = CardInstance(
        instance_id=instance_id, card_id=card_id,
        owner_id="scenario", controller_id="scenario",
    )
    inv = game.state.get_investigator("inv1")
    if engaged:
        inv.threat_area.append(instance_id)
    else:
        game.state.get_location("test_location").enemies.append(instance_id)


class TestAquinnah:
    def test_lv1_registered(self, game):
        assert "aquinnah_lv1" in game.card_registry.registered_cards

    def test_lv3_registered(self, game):
        assert "aquinnah_lv3" in game.card_registry.registered_cards

    def test_lv1_has_sanity_soak(self, game):
        data = game.state.card_database["aquinnah_lv1"]
        assert data.sanity == 4

    def test_lv1_redirects_damage_to_other_enemy(self, game):
        """敌人攻击时：横置+自受1恐惧，把攻击者伤害值转给同地点另一个敌人。"""
        aq_id = _put_aquinnah_in_play(game)
        _spawn_enemy(game, "e1")                       # 攻击者（交战）
        _spawn_enemy(game, "e2", engaged=False)        # 同地点另一个敌人

        game.damage_engine.deal_damage("inv1", damage=2, horror=1, source="e1")

        inv = game.state.get_investigator("inv1")
        aq = game.state.get_card_instance(aq_id)
        assert inv.damage == 0            # 伤害被转移
        assert inv.horror == 1            # 恐惧部分仍承受
        assert aq.exhausted is True       # 费用：横置
        assert aq.horror == 1             # 费用：安奎娜受1恐惧
        assert game.state.get_card_instance("e2").damage == 2  # 攻击者伤害值
        assert game.state.get_card_instance("e1").damage == 0

    def test_lv1_no_other_enemy_no_trigger(self, game):
        """同地点没有其他敌人时不触发（不能对攻击者本身）。"""
        aq_id = _put_aquinnah_in_play(game)
        _spawn_enemy(game, "e1")

        game.damage_engine.deal_damage("inv1", damage=2, horror=1, source="e1")

        inv = game.state.get_investigator("inv1")
        aq = game.state.get_card_instance(aq_id)
        assert inv.damage == 2
        assert inv.horror == 1
        assert aq.exhausted is False
        assert aq.horror == 0

    def test_lv1_exhausted_no_trigger(self, game):
        aq_id = _put_aquinnah_in_play(game)
        _spawn_enemy(game, "e1")
        _spawn_enemy(game, "e2", engaged=False)
        game.state.get_card_instance(aq_id).exhausted = True

        game.damage_engine.deal_damage("inv1", damage=2, horror=1, source="e1")

        inv = game.state.get_investigator("inv1")
        assert inv.damage == 2
        assert game.state.get_card_instance("e2").damage == 0

    def test_lv1_not_triggered_by_non_enemy_source(self, game):
        aq_id = _put_aquinnah_in_play(game)
        _spawn_enemy(game, "e2", engaged=False)

        game.damage_engine.deal_damage("inv1", damage=2, horror=0, source=None)

        inv = game.state.get_investigator("inv1")
        assert inv.damage == 2
        assert game.state.get_card_instance(aq_id).exhausted is False

    def test_lv3_can_target_attacker_itself(self, game):
        """lv3：任意敌人——默认把伤害反弹给攻击者本身。"""
        aq_id = _put_aquinnah_in_play(game, card_id="aquinnah_lv3")
        _spawn_enemy(game, "e1")

        game.damage_engine.deal_damage("inv1", damage=2, horror=1, source="e1")

        inv = game.state.get_investigator("inv1")
        assert inv.damage == 0
        assert inv.horror == 1
        assert game.state.get_card_instance("e1").damage == 2
        assert game.state.get_card_instance(aq_id).horror == 1

    def test_lv3_redirect_can_defeat_attacker(self, game):
        """转移伤害达到生命上限时敌人被击败。"""
        game.register_card_data(make_enemy_data(
            id="ghoul3", fight=3, health=3, evade=3, damage=3, horror=0))
        _put_aquinnah_in_play(game, card_id="aquinnah_lv3")
        _spawn_enemy(game, "e1", card_id="ghoul3")

        game.damage_engine.deal_damage("inv1", damage=3, horror=0, source="e1")

        inv = game.state.get_investigator("inv1")
        assert inv.damage == 0
        assert "e1" not in game.state.cards_in_play
        assert "e1" not in inv.threat_area
        assert "ghoul3" in game.state.scenario.encounter_discard
