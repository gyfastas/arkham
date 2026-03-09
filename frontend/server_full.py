#!/usr/bin/env python3
"""Full integration test server — 2 locations, agenda, mythos, encounter cards."""

import json
import sys
import os
import random
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from dataclasses import asdict

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.engine.game import Game
from backend.engine.event_bus import EventContext
from backend.cards.guardian.machete_lv0 import Machete
from backend.cards.guardian.forty_five_automatic_lv0 import FortyFiveAutomatic
from backend.cards.seeker.magnifying_glass_lv0 import MagnifyingGlass
from backend.cards.neutral.emergency_cache_lv0 import EmergencyCache
from backend.cards.neutral.guts_lv0 import Guts
from backend.models.enums import (
    Action, CardType, ChaosTokenType, GameEvent, Phase, PlayerClass, Skill, SlotType,
)
from backend.models.state import CardData, CardInstance, SkillValues

# Global game instance and action log
game: Game = None
action_log: list[str] = []
game_over: dict = None  # {"type": "win"/"lose", "message": "..."}

# ============================================================
# Encounter card definitions (simple treachery effects)
# ============================================================

ENCOUNTER_CARDS = {
    "rotting_remains": {
        "name": "Rotting Remains", "name_cn": "腐烂的遗骸",
        "type": "treachery", "test": "willpower", "difficulty": 3,
        "fail_effect": "horror", "fail_amount": 2,
        "text": "检定意志(3)。失败则受到2点恐惧。",
    },
    "grasping_hands": {
        "name": "Grasping Hands", "name_cn": "攫取之手",
        "type": "treachery", "test": "agility", "difficulty": 3,
        "fail_effect": "damage", "fail_amount": 2,
        "text": "检定敏捷(3)。失败则受到2点伤害。",
    },
    "crypt_chill": {
        "name": "Crypt Chill", "name_cn": "墓穴寒意",
        "type": "treachery", "test": "willpower", "difficulty": 4,
        "fail_effect": "horror", "fail_amount": 1,
        "text": "检定意志(4)。失败则受到1点恐惧并弃1张手牌。",
    },
    "obscuring_fog": {
        "name": "Obscuring Fog", "name_cn": "迷雾",
        "type": "treachery", "test": None, "difficulty": 0,
        "fail_effect": "shroud_up", "fail_amount": 1,
        "text": "当前地点隐蔽值+1直到回合结束。",
    },
    "ancient_evils": {
        "name": "Ancient Evils", "name_cn": "远古邪恶",
        "type": "treachery", "test": None, "difficulty": 0,
        "fail_effect": "doom", "fail_amount": 1,
        "text": "在密谋上放置1点毁灭标记。",
    },
    "swarm_of_rats": {
        "name": "Swarm of Rats", "name_cn": "鼠群",
        "type": "enemy",
        "fight": 1, "health": 1, "evade": 3,
        "damage": 1, "horror": 0,
        "traits": ["creature"],
        "text": "战斗1，生命1，闪避3。猎人。",
    },
}


def create_game() -> Game:
    """Initialize full scenario: 2 locations, agenda, encounter deck, enemy."""
    global action_log, game_over
    action_log = []
    game_over = None

    g = Game("the_gathering_lite")

    # --- Card Data ---

    # Investigator
    inv_data = CardData(
        id="blank_investigator", name="The Investigator", name_cn="调查员",
        type=CardType.INVESTIGATOR, card_class=PlayerClass.NEUTRAL,
        health=7, sanity=7,
        skills=SkillValues(willpower=3, intellect=3, combat=3, agility=3),
        ability="No special ability.",
    )
    g.register_card_data(inv_data)

    # Location 1: Study (start)
    study_data = CardData(
        id="study", name="Study", name_cn="书房",
        type=CardType.LOCATION, shroud=2, clue_value=3,
        connections=["hallway"],
    )
    g.register_card_data(study_data)

    # Location 2: Hallway
    hallway_data = CardData(
        id="hallway", name="Hallway", name_cn="走廊",
        type=CardType.LOCATION, shroud=1, clue_value=2,
        connections=["study"],
    )
    g.register_card_data(hallway_data)

    # Enemy: Ghoul
    ghoul_data = CardData(
        id="ghoul", name="Ghoul", name_cn="食尸鬼",
        type=CardType.ENEMY,
        enemy_fight=3, enemy_health=3, enemy_evade=3,
        enemy_damage=1, enemy_horror=1,
        traits=["humanoid", "monster"],
        keywords=["hunter"],
    )
    g.register_card_data(ghoul_data)

    # Enemy: Swarm of Rats (encounter card enemy)
    rats_data = CardData(
        id="swarm_of_rats", name="Swarm of Rats", name_cn="鼠群",
        type=CardType.ENEMY,
        enemy_fight=1, enemy_health=1, enemy_evade=3,
        enemy_damage=1, enemy_horror=0,
        traits=["creature"],
        keywords=["hunter"],
    )
    g.register_card_data(rats_data)

    # Player cards
    machete = CardData(
        id="machete_lv0", name="Machete", name_cn="弯刀",
        type=CardType.ASSET, card_class=PlayerClass.GUARDIAN, cost=3,
        slots=[SlotType.HAND], traits=["item", "weapon", "melee"],
        skill_icons={"combat": 1},
        text="+1 combat. If only 1 enemy engaged, +1 damage.",
    )
    auto45 = CardData(
        id="45_automatic_lv0", name=".45 Automatic", name_cn=".45自动手枪",
        type=CardType.ASSET, card_class=PlayerClass.GUARDIAN, cost=4,
        slots=[SlotType.HAND], traits=["item", "weapon", "firearm"],
        skill_icons={"agility": 1},
        text="Uses (4 ammo). +1 combat, +1 damage.",
        uses={"ammo": 4},
    )
    mag_glass = CardData(
        id="magnifying_glass_lv0", name="Magnifying Glass", name_cn="放大镜",
        type=CardType.ASSET, card_class=PlayerClass.SEEKER, cost=1,
        slots=[SlotType.HAND], traits=["item", "tool"],
        skill_icons={"intellect": 1},
        text="+1 intellect while investigating.",
    )
    e_cache = CardData(
        id="emergency_cache_lv0", name="Emergency Cache", name_cn="应急储备",
        type=CardType.EVENT, card_class=PlayerClass.NEUTRAL, cost=0,
        traits=["supply"],
        text="Gain 3 resources.",
    )
    guts = CardData(
        id="guts_lv0", name="Guts", name_cn="勇气",
        type=CardType.SKILL, card_class=PlayerClass.NEUTRAL, cost=None,
        skill_icons={"willpower": 2},
        traits=["innate"],
        text="If successful, draw 1 card.",
    )
    filler = CardData(
        id="filler", name="Filler Card", name_cn="填充卡",
        type=CardType.SKILL, card_class=PlayerClass.NEUTRAL, cost=None,
        skill_icons={"wild": 1},
        text="Placeholder card.",
    )

    for cd in [machete, auto45, mag_glass, e_cache, guts, filler]:
        g.register_card_data(cd)

    # Register card implementations
    g.card_registry.register_class(Machete)
    g.card_registry.register_class(FortyFiveAutomatic)
    g.card_registry.register_class(MagnifyingGlass)
    g.card_registry.register_class(EmergencyCache)
    g.card_registry.register_class(Guts)

    # Build deck
    deck = (
        ["machete_lv0"] * 2
        + ["45_automatic_lv0"] * 2
        + ["magnifying_glass_lv0"] * 2
        + ["emergency_cache_lv0"] * 2
        + ["guts_lv0"] * 2
        + ["filler"] * 10
    )
    random.shuffle(deck)

    # Add investigator and locations
    g.add_investigator("player", inv_data, deck=deck, starting_location="study")
    g.add_location("study", study_data, clues=3)
    g.add_location("hallway", hallway_data, clues=2)

    # Agenda deck (doom threshold = 5 for faster games)
    g.state.scenario.agenda_deck = ["agenda_1"]
    g.state.scenario.doom_threshold = 5

    # Encounter deck — build and shuffle
    encounter_ids = (
        ["rotting_remains"] * 2
        + ["grasping_hands"] * 2
        + ["crypt_chill"] * 1
        + ["obscuring_fog"] * 2
        + ["ancient_evils"] * 2
        + ["swarm_of_rats"] * 2
    )
    random.shuffle(encounter_ids)
    g.state.scenario.encounter_deck = encounter_ids

    # Spawn ghoul in hallway (not engaged)
    enemy_instance = CardInstance(
        instance_id="ghoul_1",
        card_id="ghoul",
        owner_id="scenario",
        controller_id="scenario",
    )
    g.state.cards_in_play["ghoul_1"] = enemy_instance
    hallway = g.state.get_location("hallway")
    hallway.enemies.append("ghoul_1")

    # Setup: draw 5, 5 resources
    g.setup()

    # Register Emergency Cache global listener
    cache_impl = EmergencyCache("cache_listener")
    cache_impl.register(g.event_bus, "cache_listener")

    # Start round 1 investigation
    g.state.scenario.current_phase = Phase.INVESTIGATION
    g.state.scenario.round_number = 1
    inv = g.state.get_investigator("player")
    inv.actions_remaining = 3

    action_log.append("=== 聚集 (简化版) ===")
    action_log.append("目标：收集书房(3)和走廊(2)共5条线索")
    action_log.append(f"密谋：毁灭达到{g.state.scenario.doom_threshold}时游戏失败")
    action_log.append("书房←→走廊 | 食尸鬼(猎人)在走廊")
    action_log.append(f"=== 第1轮 调查阶段 ===")
    return g


def serialize_state(g: Game) -> dict:
    """Serialize game state to JSON-friendly dict."""
    inv = g.state.get_investigator("player")
    current_loc = g.state.get_location(inv.location_id)

    # All locations
    locations = {}
    for loc_id, loc in g.state.locations.items():
        locations[loc_id] = {
            "name": loc.card_data.name,
            "name_cn": loc.card_data.name_cn,
            "shroud": loc.shroud,
            "clues": loc.clues,
            "connections": loc.connections,
            "enemies_here": len(loc.enemies),
            "is_current": loc_id == inv.location_id,
        }

    # Hand cards
    hand = []
    for card_id in inv.hand:
        cd = g.state.get_card_data(card_id)
        if cd:
            hand.append({
                "id": cd.id, "name": cd.name, "name_cn": cd.name_cn,
                "type": cd.type.value, "cost": cd.cost,
                "text": cd.text, "class": cd.card_class.value,
                "slots": [s.value for s in cd.slots],
                "skill_icons": cd.skill_icons,
                "traits": cd.traits,
            })

    # Play area
    play_area = []
    for inst_id in inv.play_area:
        ci = g.state.get_card_instance(inst_id)
        if ci:
            cd = g.state.get_card_data(ci.card_id)
            play_area.append({
                "instance_id": ci.instance_id,
                "id": ci.card_id,
                "name": cd.name if cd else ci.card_id,
                "name_cn": cd.name_cn if cd else "",
                "exhausted": ci.exhausted,
                "uses": ci.uses,
                "slots": [s.value for s in ci.slot_used],
            })

    # Enemies at current location + engaged
    enemies = []
    for inst_id in inv.threat_area:
        ci = g.state.get_card_instance(inst_id)
        if ci:
            cd = g.state.get_card_data(ci.card_id)
            enemies.append(_enemy_dict(ci, cd, engaged=True))
    if current_loc:
        for inst_id in current_loc.enemies:
            ci = g.state.get_card_instance(inst_id)
            if ci:
                cd = g.state.get_card_data(ci.card_id)
                enemies.append(_enemy_dict(ci, cd, engaged=False))

    scenario = g.state.scenario
    return {
        "investigator": {
            "health": inv.health,
            "sanity": inv.sanity,
            "damage": inv.damage,
            "horror": inv.horror,
            "resources": inv.resources,
            "clues": inv.clues,
            "actions_remaining": inv.actions_remaining,
            "hand_count": len(inv.hand),
            "deck_count": len(inv.deck),
            "discard_count": len(inv.discard),
            "defeated": inv.is_defeated,
            "location_id": inv.location_id,
        },
        "location": {
            "id": inv.location_id,
            "name": current_loc.card_data.name if current_loc else "",
            "name_cn": current_loc.card_data.name_cn if current_loc else "",
            "shroud": current_loc.shroud if current_loc else 0,
            "clues": current_loc.clues if current_loc else 0,
            "connections": current_loc.connections if current_loc else [],
        },
        "locations": locations,
        "hand": hand,
        "play_area": play_area,
        "enemies": enemies,
        "phase": scenario.current_phase.name,
        "round": scenario.round_number,
        "doom": scenario.doom_on_agenda,
        "doom_threshold": scenario.doom_threshold,
        "encounter_deck_count": len(scenario.encounter_deck),
        "total_clues_needed": 5,
        "game_over": game_over,
        "log": action_log[-30:],
    }


def _enemy_dict(ci, cd, engaged):
    return {
        "instance_id": ci.instance_id,
        "id": ci.card_id,
        "name": cd.name if cd else ci.card_id,
        "name_cn": cd.name_cn if cd else "",
        "fight": cd.enemy_fight if cd else 0,
        "health": cd.enemy_health if cd else 0,
        "evade": cd.enemy_evade if cd else 0,
        "damage_dealt": cd.enemy_damage if cd else 0,
        "horror_dealt": cd.enemy_horror if cd else 0,
        "current_damage": ci.damage,
        "exhausted": ci.exhausted,
        "engaged": engaged,
    }


# ============================================================
# Encounter card resolution
# ============================================================

def resolve_encounter_card(card_id: str) -> str:
    """Resolve an encounter card drawn from the deck."""
    global game, action_log
    inv = game.state.get_investigator("player")
    enc = ENCOUNTER_CARDS.get(card_id)
    if not enc:
        return f"未知遭遇卡: {card_id}"

    action_log.append(f"📜 遭遇卡: {enc['name_cn']} ({enc['name']})")
    action_log.append(f"   {enc['text']}")

    if enc["type"] == "enemy":
        # Spawn enemy at investigator's location, engaged
        inst_id = game.state.next_instance_id()
        enemy_inst = CardInstance(
            instance_id=inst_id,
            card_id=card_id,
            owner_id="scenario",
            controller_id="scenario",
        )
        game.state.cards_in_play[inst_id] = enemy_inst
        inv.threat_area.append(inst_id)
        action_log.append(f"👹 {enc['name_cn']}出现并与你交战！")
        return f"敌人出现: {enc['name_cn']}"

    # Treachery
    effect = enc["fail_effect"]

    if effect == "doom":
        game.state.scenario.doom_on_agenda += enc["fail_amount"]
        action_log.append(f"💀 密谋上增加{enc['fail_amount']}点毁灭 (当前: {game.state.scenario.doom_on_agenda}/{game.state.scenario.doom_threshold})")
        check_agenda()
        return f"+{enc['fail_amount']} doom"

    if effect == "shroud_up":
        loc = game.state.get_location(inv.location_id)
        if loc:
            # Temporarily increase shroud (we'll track via action_log only)
            action_log.append(f"🌫️ 当前地点隐蔽值暂时+1")
        return "shroud+1"

    # Skill test treachery
    if enc.get("test"):
        skill_map = {"willpower": Skill.WILLPOWER, "agility": Skill.AGILITY,
                     "intellect": Skill.INTELLECT, "combat": Skill.COMBAT}
        skill = skill_map.get(enc["test"], Skill.WILLPOWER)
        difficulty = enc["difficulty"]

        result = game.skill_test_engine.run_test(
            investigator_id="player",
            skill_type=skill,
            difficulty=difficulty,
        )

        if result.success:
            action_log.append(f"✅ 检定成功！({result.modified_skill} vs {difficulty})")
            return "检定成功"
        else:
            action_log.append(f"❌ 检定失败 ({result.modified_skill} vs {difficulty})")
            if effect == "horror":
                game.damage_engine.deal_damage("player", horror=enc["fail_amount"])
                action_log.append(f"😱 受到{enc['fail_amount']}点恐惧")
            elif effect == "damage":
                game.damage_engine.deal_damage("player", damage=enc["fail_amount"])
                action_log.append(f"💥 受到{enc['fail_amount']}点伤害")
            return f"检定失败: {effect}"

    return "resolved"


def check_agenda():
    """Check if agenda should advance (game over)."""
    global game_over
    scenario = game.state.scenario
    if scenario.doom_on_agenda >= scenario.doom_threshold:
        game_over = {
            "type": "lose",
            "message": f"毁灭标记达到{scenario.doom_threshold}！黑暗笼罩了一切..."
        }
        action_log.append(f"💀💀💀 密谋推进！毁灭达到{scenario.doom_threshold}！游戏失败！")


def check_win():
    """Check if player collected enough clues to win."""
    global game_over
    inv = game.state.get_investigator("player")
    if inv.clues >= 5:
        game_over = {
            "type": "win",
            "message": f"你收集了{inv.clues}条线索，揭开了真相！"
        }
        action_log.append(f"🎉🎉🎉 你收集了{inv.clues}条线索！调查成功！")


# ============================================================
# Action handling (same as server.py but with multi-location)
# ============================================================

def handle_action(data: dict) -> dict:
    """Process a player action."""
    global game, action_log
    inv = game.state.get_investigator("player")

    if inv.is_defeated or game_over:
        return {"success": False, "message": "游戏已结束"}

    action_name = data.get("action", "").upper()
    result = {"success": False, "message": "未知行动"}

    if action_name == "FIGHT":
        enemy_id = data.get("enemy_instance_id")
        weapon_id = data.get("weapon_instance_id")
        committed = data.get("committed_cards", [])
        if not enemy_id:
            location = game.state.get_location(inv.location_id)
            if inv.threat_area:
                enemy_id = inv.threat_area[0]
            elif location and location.enemies:
                enemy_id = location.enemies[0]
            else:
                return {"success": False, "message": "没有可攻击的敌人"}

        # Auto-engage if at location but not engaged
        if enemy_id not in inv.threat_area:
            location = game.state.get_location(inv.location_id)
            if location and enemy_id in location.enemies:
                location.enemies.remove(enemy_id)
                inv.threat_area.append(enemy_id)
                action_log.append(f"🎯 自动与敌人交战")

        enemy = game.state.get_card_instance(enemy_id)
        enemy_data = game.state.get_card_data(enemy.card_id) if enemy else None
        old_damage = enemy.damage if enemy else 0
        old_inv_damage = inv.damage
        old_inv_horror = inv.horror

        if committed:
            names = [game.state.get_card_data(cid).name_cn for cid in committed if game.state.get_card_data(cid)]
            action_log.append(f"📋 投入卡牌: {', '.join(names)}")

        ok = game.action_resolver.perform_action(
            "player", Action.FIGHT,
            enemy_instance_id=enemy_id,
            weapon_instance_id=weapon_id,
            committed_cards=committed,
        )
        if ok:
            if enemy_id not in game.state.cards_in_play:
                action_log.append(f"⚔️ 战斗成功！{enemy_data.name_cn}被击败！")
            elif enemy.damage > old_damage:
                action_log.append(f"⚔️ 战斗成功！对{enemy_data.name_cn}造成{enemy.damage - old_damage}点伤害 ({enemy.damage}/{enemy_data.enemy_health})")
            else:
                action_log.append(f"⚔️ 战斗失败！未命中{enemy_data.name_cn}")
            if inv.damage > old_inv_damage or inv.horror > old_inv_horror:
                action_log.append(f"💥 借机攻击！受到{inv.damage - old_inv_damage}伤害/{inv.horror - old_inv_horror}恐惧")
            result = {"success": True, "message": action_log[-1]}
        else:
            result = {"success": False, "message": "无法执行战斗"}

    elif action_name == "EVADE":
        enemy_id = data.get("enemy_instance_id")
        committed = data.get("committed_cards", [])
        if not enemy_id and inv.threat_area:
            enemy_id = inv.threat_area[0]
        if not enemy_id:
            return {"success": False, "message": "没有可闪避的敌人"}

        enemy = game.state.get_card_instance(enemy_id)
        enemy_data = game.state.get_card_data(enemy.card_id) if enemy else None

        if committed:
            names = [game.state.get_card_data(cid).name_cn for cid in committed if game.state.get_card_data(cid)]
            action_log.append(f"📋 投入卡牌: {', '.join(names)}")

        ok = game.action_resolver.perform_action(
            "player", Action.EVADE, enemy_instance_id=enemy_id,
            committed_cards=committed,
        )
        if ok:
            if enemy_id not in inv.threat_area:
                action_log.append(f"🛡️ 闪避成功！{enemy_data.name_cn}被甩开并消耗")
            else:
                action_log.append(f"🛡️ 闪避失败！{enemy_data.name_cn}仍在纠缠")
            result = {"success": True, "message": action_log[-1]}
        else:
            result = {"success": False, "message": "无法闪避"}

    elif action_name == "INVESTIGATE":
        location = game.state.get_location(inv.location_id)
        committed = data.get("committed_cards", [])
        old_clues = inv.clues

        if committed:
            names = [game.state.get_card_data(cid).name_cn for cid in committed if game.state.get_card_data(cid)]
            action_log.append(f"📋 投入卡牌: {', '.join(names)}")

        ok = game.action_resolver.perform_action(
            "player", Action.INVESTIGATE, committed_cards=committed,
        )
        if ok:
            if inv.clues > old_clues:
                action_log.append(f"🔍 调查成功！发现1条线索 (共{inv.clues}条)")
                check_win()
            else:
                action_log.append(f"🔍 调查失败！")
            result = {"success": True, "message": action_log[-1]}
        else:
            result = {"success": False, "message": "无法调查"}

    elif action_name == "DRAW":
        old_hand = len(inv.hand)
        old_inv_damage = inv.damage
        old_inv_horror = inv.horror
        ok = game.action_resolver.perform_action("player", Action.DRAW)
        if ok:
            if len(inv.hand) > old_hand:
                new_card_id = inv.hand[-1]
                cd = game.state.get_card_data(new_card_id)
                name = cd.name_cn if cd else new_card_id
                action_log.append(f"🃏 抽到: {name}")
            else:
                action_log.append(f"🃏 抽牌（牌组已空）")
            if inv.damage > old_inv_damage or inv.horror > old_inv_horror:
                action_log.append(f"💥 借机攻击！受到{inv.damage - old_inv_damage}伤害/{inv.horror - old_inv_horror}恐惧")
            result = {"success": True, "message": action_log[-1]}
        else:
            result = {"success": False, "message": "无法抽牌"}

    elif action_name == "RESOURCE":
        old_inv_damage = inv.damage
        old_inv_horror = inv.horror
        ok = game.action_resolver.perform_action("player", Action.RESOURCE)
        if ok:
            action_log.append(f"💰 获得1资源 (共{inv.resources})")
            if inv.damage > old_inv_damage or inv.horror > old_inv_horror:
                action_log.append(f"💥 借机攻击！受到{inv.damage - old_inv_damage}伤害/{inv.horror - old_inv_horror}恐惧")
            result = {"success": True, "message": action_log[-1]}
        else:
            result = {"success": False, "message": "无法��取资源"}

    elif action_name == "PLAY":
        card_id = data.get("card_id")
        if not card_id:
            return {"success": False, "message": "未指定卡牌"}
        cd = game.state.get_card_data(card_id)
        if not cd:
            return {"success": False, "message": f"未知卡牌: {card_id}"}

        old_inv_damage = inv.damage
        old_inv_horror = inv.horror
        ok = game.action_resolver.perform_action("player", Action.PLAY, card_id=card_id)
        if ok:
            action_log.append(f"🎴 打出: {cd.name_cn} ({cd.name})")
            if inv.damage > old_inv_damage or inv.horror > old_inv_horror:
                action_log.append(f"💥 借机攻击！受到{inv.damage - old_inv_damage}伤害/{inv.horror - old_inv_horror}恐惧")
            result = {"success": True, "message": action_log[-1]}
        else:
            if inv.resources < (cd.cost or 0):
                result = {"success": False, "message": f"资源不足！需要{cd.cost}，当前{inv.resources}"}
            else:
                result = {"success": False, "message": f"无法打出{cd.name_cn}"}

    elif action_name == "MOVE":
        destination = data.get("destination")
        if not destination:
            return {"success": False, "message": "未指定目的地"}
        old_inv_damage = inv.damage
        old_inv_horror = inv.horror
        ok = game.action_resolver.perform_action(
            "player", Action.MOVE, destination=destination,
        )
        if ok:
            dest_loc = game.state.get_location(destination)
            action_log.append(f"🚶 移动到{dest_loc.card_data.name_cn if dest_loc else destination}")
            if inv.damage > old_inv_damage or inv.horror > old_inv_horror:
                action_log.append(f"💥 借机攻击！受到{inv.damage - old_inv_damage}伤害/{inv.horror - old_inv_horror}恐惧")
            result = {"success": True, "message": action_log[-1]}
        else:
            result = {"success": False, "message": "无法移动到该地点"}

    elif action_name == "ENGAGE":
        enemy_id = data.get("enemy_instance_id")
        if not enemy_id:
            return {"success": False, "message": "未指定敌人"}
        ok = game.action_resolver.perform_action(
            "player", Action.ENGAGE, enemy_instance_id=enemy_id,
        )
        if ok:
            action_log.append(f"🎯 与敌人交战")
            result = {"success": True, "message": action_log[-1]}

    return result


def handle_end_turn() -> dict:
    """End investigation phase, run enemy + upkeep + mythos."""
    global game, action_log, game_over
    inv = game.state.get_investigator("player")

    if inv.is_defeated or game_over:
        return {"message": "游戏已结束"}

    # === Enemy Phase ===
    action_log.append("--- 敌人阶段 ---")
    old_damage = inv.damage
    old_horror = inv.horror

    game.enemy_phase.resolve()

    if inv.damage > old_damage or inv.horror > old_horror:
        action_log.append(f"👹 敌人攻击！受到{inv.damage - old_damage}伤害/{inv.horror - old_horror}恐惧 (HP:{inv.remaining_health}/{inv.health} SAN:{inv.remaining_sanity}/{inv.sanity})")
    else:
        action_log.append("敌人未攻击（已消耗或无敌人）")

    if inv.is_defeated:
        action_log.append("💀 调查员被击败！游戏结束！")
        game_over = {"type": "lose", "message": "调查员被击败！"}
        return {"message": "调查员被击败！"}

    # === Upkeep Phase ===
    action_log.append("--- 刷新阶段 ---")
    game.upkeep_phase.resolve()
    action_log.append(f"♻️ 刷新：就绪所有卡牌，抽1牌，+1资源 (资源:{inv.resources}，手牌:{len(inv.hand)})")

    # === New Round ===
    game.state.scenario.round_number += 1

    # === Mythos Phase (skip round 1 already handled) ===
    action_log.append("--- 神话阶段 ---")

    # 1. Place doom
    game.state.scenario.doom_on_agenda += 1
    action_log.append(f"💀 毁灭+1 (当前: {game.state.scenario.doom_on_agenda}/{game.state.scenario.doom_threshold})")
    check_agenda()
    if game_over:
        return {"message": game_over["message"]}

    # 2. Draw encounter card
    scenario = game.state.scenario
    if scenario.encounter_deck:
        enc_id = scenario.encounter_deck.pop(0)
        scenario.encounter_discard.append(enc_id)
        resolve_encounter_card(enc_id)

        if inv.is_defeated:
            action_log.append("💀 调查员被击败！游戏结束！")
            game_over = {"type": "lose", "message": "调查员被遭遇卡击败！"}
            return {"message": "调查员被击败！"}
    else:
        # Shuffle discard back
        scenario.encounter_deck = list(scenario.encounter_discard)
        random.shuffle(scenario.encounter_deck)
        scenario.encounter_discard.clear()
        action_log.append("♻️ 遭遇弃牌堆洗回")

    # Begin new investigation phase
    inv.actions_remaining = 3
    inv.has_taken_turn = False
    game.state.scenario.current_phase = Phase.INVESTIGATION

    action_log.append(f"=== 第{game.state.scenario.round_number}轮 调查阶段 ===")
    return {"message": f"进入第{game.state.scenario.round_number}轮"}


# ============================================================
# HTTP Server
# ============================================================

class GameHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/":
            self._serve_html()
        elif self.path == "/api/state":
            self._json_response(serialize_state(game))
        else:
            self.send_error(404)

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length else b"{}"
        data = json.loads(body) if body else {}

        if self.path == "/api/setup":
            global game
            game = create_game()
            self._json_response({"message": "游戏已初始化", "state": serialize_state(game)})
        elif self.path == "/api/action":
            result = handle_action(data)
            result["state"] = serialize_state(game)
            self._json_response(result)
        elif self.path == "/api/end-turn":
            result = handle_end_turn()
            result["state"] = serialize_state(game)
            self._json_response(result)
        else:
            self.send_error(404)

    def _json_response(self, data):
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def _serve_html(self):
        html_path = Path(__file__).parent / "scenario.html"
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html_path.read_bytes())

    def log_message(self, format, *args):
        pass


def main():
    global game
    game = create_game()
    port = 8908
    server = HTTPServer(("0.0.0.0", port), GameHandler)
    print(f"Arkham Horror LCG — Full Scenario Test")
    print(f"http://localhost:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")


if __name__ == "__main__":
    main()
