#!/usr/bin/env python3
"""Simple HTTP server for Arkham Horror LCG frontend testing."""

import json
import sys
import os
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


def create_game() -> Game:
    """Initialize a test game with 1 investigator, 1 location, 1 enemy."""
    global action_log
    action_log = []

    g = Game("test_scenario")

    # --- Card Data ---

    # Blank investigator: all stats 3, 7/7
    inv_data = CardData(
        id="blank_investigator", name="The Investigator", name_cn="调查员",
        type=CardType.INVESTIGATOR, card_class=PlayerClass.NEUTRAL,
        health=7, sanity=7,
        skills=SkillValues(willpower=3, intellect=3, combat=3, agility=3),
        ability="No special ability.",
    )
    g.register_card_data(inv_data)

    # Location: Study
    study_data = CardData(
        id="study", name="Study", name_cn="书房",
        type=CardType.LOCATION, shroud=2, clue_value=3,
        connections=[],
    )
    g.register_card_data(study_data)

    # Enemy: Ghoul
    ghoul_data = CardData(
        id="ghoul", name="Ghoul", name_cn="食尸鬼",
        type=CardType.ENEMY,
        enemy_fight=3, enemy_health=3, enemy_evade=3,
        enemy_damage=1, enemy_horror=1,
        traits=["humanoid", "monster"],
        keywords=[],
    )
    g.register_card_data(ghoul_data)

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
    # Filler cards
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

    # Build deck: 2x each real card + fillers
    deck = (
        ["machete_lv0"] * 2
        + ["45_automatic_lv0"] * 2
        + ["magnifying_glass_lv0"] * 2
        + ["emergency_cache_lv0"] * 2
        + ["guts_lv0"] * 2
        + ["filler"] * 10
    )
    import random
    random.shuffle(deck)

    # Add investigator and location
    g.add_investigator("player", inv_data, deck=deck, starting_location="study")
    g.add_location("study", study_data, clues=3)

    # Spawn enemy at location (engaged with investigator)
    enemy_instance = CardInstance(
        instance_id="ghoul_1",
        card_id="ghoul",
        owner_id="scenario",
        controller_id="scenario",
    )
    g.state.cards_in_play["ghoul_1"] = enemy_instance
    inv = g.state.get_investigator("player")
    inv.threat_area.append("ghoul_1")

    # Setup: draw 5 cards, 5 resources
    g.setup()

    # Register event listener for Emergency Cache (events need global listener)
    cache_impl = EmergencyCache("cache_listener")
    cache_impl.register(g.event_bus, "cache_listener")

    # Set phase to investigation
    g.state.scenario.current_phase = Phase.INVESTIGATION
    g.state.scenario.round_number = 1
    inv.actions_remaining = 3

    action_log.append("游戏开始！你在书房中，面对一只食尸鬼。你有3个行动点。")
    return g


def serialize_state(g: Game) -> dict:
    """Serialize game state to JSON-friendly dict."""
    inv = g.state.get_investigator("player")
    location = g.state.get_location("study")

    # Hand cards with details
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

    # Play area (assets in play)
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

    # Enemies
    enemies = []
    # Engaged enemies
    for inst_id in inv.threat_area:
        ci = g.state.get_card_instance(inst_id)
        if ci:
            cd = g.state.get_card_data(ci.card_id)
            enemies.append({
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
                "engaged": True,
            })
    # Unengaged at location
    for inst_id in location.enemies:
        ci = g.state.get_card_instance(inst_id)
        if ci:
            cd = g.state.get_card_data(ci.card_id)
            enemies.append({
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
                "engaged": False,
            })

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
        },
        "location": {
            "name": location.card_data.name,
            "name_cn": location.card_data.name_cn,
            "shroud": location.shroud,
            "clues": location.clues,
        },
        "hand": hand,
        "play_area": play_area,
        "enemies": enemies,
        "phase": g.state.scenario.current_phase.name,
        "round": g.state.scenario.round_number,
        "log": action_log[-20:],  # Last 20 log entries
    }


def handle_action(data: dict) -> dict:
    """Process a player action and return result."""
    global game, action_log
    inv = game.state.get_investigator("player")

    if inv.is_defeated:
        return {"success": False, "message": "调查员已被击败！"}

    action_name = data.get("action", "").upper()
    result = {"success": False, "message": "未知行动"}

    if action_name == "FIGHT":
        enemy_id = data.get("enemy_instance_id")
        weapon_id = data.get("weapon_instance_id")
        committed = data.get("committed_cards", [])
        if not enemy_id:
            # Auto-select: first engaged, then first at location
            location = game.state.get_location(inv.location_id)
            if inv.threat_area:
                enemy_id = inv.threat_area[0]
            elif location and location.enemies:
                enemy_id = location.enemies[0]
            else:
                return {"success": False, "message": "没有可攻击的敌人"}

        # Auto-engage if enemy is at location but not engaged
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
            # Check what happened
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
        was_engaged = enemy_id in inv.threat_area

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
            result = {"success": False, "message": "无法获取资源"}

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
    """End investigation phase, run enemy + upkeep."""
    global game, action_log
    inv = game.state.get_investigator("player")

    if inv.is_defeated:
        return {"message": "调查员已被击败！"}

    # Enemy phase
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
        return {"message": "调查员被击败！"}

    # Upkeep phase
    action_log.append("--- 刷新阶段 ---")
    old_hand = len(inv.hand)
    old_res = inv.resources
    game.upkeep_phase.resolve()

    action_log.append(f"♻️ 刷新：就绪所有卡牌，抽1牌，+1资源 (资源:{inv.resources}，手牌:{len(inv.hand)})")

    # New round
    game.state.scenario.round_number += 1
    inv.actions_remaining = 3
    inv.has_taken_turn = False
    game.state.scenario.current_phase = Phase.INVESTIGATION

    # Respawn ghoul if defeated
    if "ghoul_1" not in game.state.cards_in_play:
        ghoul_instance = CardInstance(
            instance_id="ghoul_1",
            card_id="ghoul",
            owner_id="scenario",
            controller_id="scenario",
        )
        game.state.cards_in_play["ghoul_1"] = ghoul_instance
        inv.threat_area.append("ghoul_1")
        action_log.append("👹 新的食尸鬼出现了！")

    action_log.append(f"=== 第{game.state.scenario.round_number}轮 调查阶段 ===")
    return {"message": f"进入第{game.state.scenario.round_number}轮"}


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
        html_path = Path(__file__).parent / "index.html"
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html_path.read_bytes())

    def log_message(self, format, *args):
        pass  # Suppress access logs


def main():
    global game
    game = create_game()
    port = 8907
    server = HTTPServer(("0.0.0.0", port), GameHandler)
    print(f"Arkham Horror LCG Test Server")
    print(f"http://localhost:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")


if __name__ == "__main__":
    main()
