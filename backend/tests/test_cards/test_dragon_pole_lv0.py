"""Tests for Dragon Pole (Level 0). (08060)

+1额外法术槽位；攻击时每个被占用的法术槽位+1战斗，≥2个被占用时+1伤害。
"""

import pytest
from backend.cards.mystic.dragon_pole_lv0 import DragonPole
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import (
    Action, CardType, ChaosTokenType, GameEvent, PlayerClass, Skill, SlotType,
)
from backend.models.state import CardData, CardInstance
from backend.tests.conftest import (
    make_asset_data, make_enemy_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data(combat=3)
    g.register_card_data(inv_data)
    loc = make_location_data()
    g.register_card_data(loc)

    pole_data = CardData(
        id="dragon_pole_lv0", name="Dragon Pole", name_cn="咏春棍",
        type=CardType.ASSET, card_class=PlayerClass.MYSTIC, cost=3,
        slots=[SlotType.HAND, SlotType.HAND], traits=["item", "weapon", "melee"],
        skill_icons={"combat": 1},
    )
    g.register_card_data(pole_data)
    g.register_card_data(make_asset_data(
        id="spell_asset", name="Spell", slots=[SlotType.ARCANE],
        traits=["spell"],
    ))
    g.register_card_data(make_enemy_data(fight=3, health=6))

    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)
    g.card_registry.register_class(DragonPole)
    return g


def _equip(game):
    inv = game.state.get_investigator("inv1")
    instance_id = "inst_pole"
    inst = CardInstance(
        instance_id=instance_id, card_id="dragon_pole_lv0",
        owner_id="inv1", controller_id="inv1",
        slot_used=[SlotType.HAND, SlotType.HAND],
    )
    game.state.cards_in_play[instance_id] = inst
    inv.play_area.append(instance_id)
    game.card_registry.activate_card("dragon_pole_lv0", instance_id, game.event_bus)
    # 入场事件：获得额外法术槽位
    game.event_bus.emit(EventContext(
        game_state=game.state, event=GameEvent.CARD_ENTERS_PLAY,
        investigator_id="inv1", target=instance_id,
        extra={"card_id": "dragon_pole_lv0"},
    ))
    return instance_id


def _fill_arcane(game, count):
    """给 inv1 装备 count 个法术槽支援（占用 slot manager 的法术槽）。"""
    inv = game.state.get_investigator("inv1")
    slot_mgr = game.slot_managers["inv1"]
    for i in range(count):
        iid = f"inst_spell_{i}"
        inst = CardInstance(
            instance_id=iid, card_id="spell_asset",
            owner_id="inv1", controller_id="inv1",
            slot_used=[SlotType.ARCANE],
        )
        game.state.cards_in_play[iid] = inst
        inv.play_area.append(iid)
        slot_mgr.occupy(iid, [SlotType.ARCANE], ["spell"])


def _spawn_enemy(game):
    enemy = CardInstance(
        instance_id="enemy_1", card_id="test_enemy",
        owner_id="scenario", controller_id="scenario",
    )
    game.state.cards_in_play["enemy_1"] = enemy
    game.state.get_investigator("inv1").threat_area.append("enemy_1")
    return enemy


class TestDragonPole:
    def test_grants_extra_arcane_slot(self, game):
        _equip(game)
        slot_mgr = game.slot_managers["inv1"]
        assert slot_mgr.bonus_slots.get(SlotType.ARCANE) == 1

    def test_combat_bonus_per_filled_arcane(self, game):
        """2个法术槽被占用：+2战斗；命中造成+1伤害（共2点）。"""
        pole_id = _equip(game)
        _fill_arcane(game, 2)
        enemy = _spawn_enemy(game)
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]

        inv = game.state.get_investigator("inv1")
        inv.actions_remaining = 3
        ok = game.action_resolver.perform_action(
            "inv1", Action.FIGHT,
            enemy_instance_id="enemy_1", weapon_instance_id=pole_id,
        )
        assert ok is True
        # 战斗 3 + 2 = 5 vs 3 成功；伤害 1 + 1 = 2
        assert enemy.damage == 2

    def test_single_filled_arcane_no_bonus_damage(self, game):
        """仅1个法术槽被占用：+1战斗，无额外伤害。"""
        pole_id = _equip(game)
        _fill_arcane(game, 1)
        enemy = _spawn_enemy(game)
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]

        inv = game.state.get_investigator("inv1")
        inv.actions_remaining = 3
        game.action_resolver.perform_action(
            "inv1", Action.FIGHT,
            enemy_instance_id="enemy_1", weapon_instance_id=pole_id,
        )
        # 战斗 3 + 1 = 4 vs 3 成功；伤害 1（无加成）
        assert enemy.damage == 1

    def test_leaves_play_removes_bonus_slot(self, game):
        pole_id = _equip(game)
        game.event_bus.emit(EventContext(
            game_state=game.state, event=GameEvent.CARD_LEAVES_PLAY,
            investigator_id="inv1", target=pole_id,
            extra={"card_id": "dragon_pole_lv0"},
        ))
        slot_mgr = game.slot_managers["inv1"]
        assert slot_mgr.bonus_slots.get(SlotType.ARCANE) is None
