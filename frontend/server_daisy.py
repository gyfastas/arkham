#!/usr/bin/env python3
"""Daisy Walker scenario — 失落知识的图书馆 (The Lost Library).

3 locations, 3 enemy types, 12 encounter cards, 30-card deck.
Daisy gets +1 action (Tome-only), Necronomicon revelation, 7 clues to win.
"""

import json
import sys
import os
import random
from collections import Counter
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from dataclasses import asdict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.engine.game import Game
from backend.engine.event_bus import EventContext
from backend.cards.seeker.daisy_walker import DaisyWalker
from backend.cards.seeker.daisys_tote_bag import DaisysToteBag
from backend.cards.seeker.magnifying_glass_lv0 import MagnifyingGlass
from backend.cards.seeker.deduction_lv0 import Deduction
from backend.cards.seeker.dr_milan_christopher_lv0 import DrMilanChristopher
from backend.cards.seeker.working_a_hunch_lv0 import WorkingAHunch
from backend.cards.seeker.old_book_of_lore_lv0 import OldBookOfLore
from backend.cards.seeker.hyperawareness_lv0 import Hyperawareness
from backend.cards.seeker.research_librarian_lv0 import ResearchLibrarian
from backend.cards.seeker.encyclopedia_lv2 import Encyclopedia
from backend.cards.seeker.medical_texts_lv0 import MedicalTexts
from backend.cards.neutral.the_necronomicon import TheNecronomicon
from backend.cards.neutral.knife_lv0 import Knife
from backend.cards.neutral.guts_lv0 import Guts
from backend.cards.neutral.perception_lv0 import Perception
from backend.cards.neutral.manual_dexterity_lv0 import ManualDexterity
from backend.cards.neutral.unexpected_courage_lv0 import UnexpectedCourage
from backend.cards.neutral.emergency_cache_lv0 import EmergencyCache
from backend.models.enums import (
    Action, CardType, ChaosTokenType, GameEvent, Phase, PlayerClass, Skill, SlotType,
)
from backend.models.investigator import InvestigatorCard, DeckRequirement
from backend.models.state import CardData, CardInstance, SkillValues

# Global state
game: Game = None
action_log: list[str] = []
game_over: dict = None
necronomicon_instance: TheNecronomicon = None  # For activate calls

# ============================================================
# Encounter cards
# ============================================================

ENCOUNTER_CARDS = {
    "whispering_voices": {
        "name": "Whispering Voices", "name_cn": "窃窃私语",
        "type": "treachery", "test": "willpower", "difficulty": 3,
        "fail_effect": "horror", "fail_amount": 2,
        "text": "检定意志(3)。失败则受到2点恐惧。",
    },
    "grasping_tentacles": {
        "name": "Grasping Tentacles", "name_cn": "纠缠触手",
        "type": "treachery", "test": "agility", "difficulty": 3,
        "fail_effect": "damage_and_discard", "fail_amount": 1,
        "text": "检定敏捷(3)。失败则受到1点伤害并弃1张手牌。",
    },
    "ancient_evils": {
        "name": "Ancient Evils", "name_cn": "远古邪恶",
        "type": "treachery", "test": None, "difficulty": 0,
        "fail_effect": "doom", "fail_amount": 1,
        "doom_check_immediate": True,
        "text": "在密谋上放置1点毁灭标记。",
    },
    "forbidden_knowledge_enc": {
        "name": "Forbidden Knowledge", "name_cn": "禁忌知识",
        "type": "treachery", "test": "intellect", "difficulty": 4,
        "fail_effect": "horror_and_doom", "fail_amount": 1,
        "doom_check_immediate": True,
        "text": "检定智力(4)。失败则受到1点恐惧并在密谋上放置1点毁灭。",
    },
    "animated_tome_enc": {
        "name": "Animated Tome", "name_cn": "活化典籍",
        "type": "enemy",
        "fight": 3, "health": 2, "evade": 2,
        "damage": 1, "horror": 1,
        "traits": ["monster"],
        "text": "战斗3，生命2，闪避2。",
    },
}

# ============================================================
# Game creation
# ============================================================

def create_game() -> Game:
    global action_log, game_over, necronomicon_instance
    action_log = []
    game_over = None
    necronomicon_instance = None

    g = Game("lost_library")

    # --- Investigator ---
    inv_card = InvestigatorCard(
        id="daisy_walker", name="Daisy Walker", name_cn="黛西·沃克",
        card_class=PlayerClass.SEEKER,
        health=5, sanity=9,
        skills=SkillValues(willpower=3, intellect=5, combat=2, agility=2),
        ability="每回合+1行动（仅限典籍）。",
        elder_sign="+0，成功时每控制1本典籍抽1张牌。",
        deck_requirement=DeckRequirement(
            size=30,
            allowed_classes=["seeker", "neutral"],
            max_level=5,
            required_cards=["daisys_tote_bag"],
            weaknesses=["the_necronomicon"],
        ),
        signature_cards=["daisys_tote_bag"],
        weaknesses=["the_necronomicon"],
    )

    # --- Locations ---
    reading_room = CardData(
        id="reading_room", name="Reading Room", name_cn="阅览室",
        type=CardType.LOCATION, shroud=2, clue_value=3,
        connections=["restricted_section"],
    )
    restricted_section = CardData(
        id="restricted_section", name="Restricted Section", name_cn="禁区",
        type=CardType.LOCATION, shroud=3, clue_value=4,
        connections=["reading_room", "archive"],
    )
    archive = CardData(
        id="archive", name="Archive", name_cn="档案室",
        type=CardType.LOCATION, shroud=1, clue_value=2,
        connections=["restricted_section"],
    )
    for loc in [reading_room, restricted_section, archive]:
        g.register_card_data(loc)

    # --- Enemies ---
    spectral_librarian = CardData(
        id="spectral_librarian", name="Spectral Librarian", name_cn="幽灵馆员",
        type=CardType.ENEMY,
        enemy_fight=2, enemy_health=3, enemy_evade=4,
        enemy_damage=1, enemy_horror=2,
        traits=["monster", "geist"],
        keywords=["hunter"],
    )
    animated_tome = CardData(
        id="animated_tome", name="Animated Tome", name_cn="活化典籍",
        type=CardType.ENEMY,
        enemy_fight=3, enemy_health=2, enemy_evade=2,
        enemy_damage=1, enemy_horror=1,
        traits=["monster"],
    )
    shadow_acolyte = CardData(
        id="shadow_acolyte", name="Shadow Acolyte", name_cn="暗影侍从",
        type=CardType.ENEMY,
        enemy_fight=4, enemy_health=3, enemy_evade=3,
        enemy_damage=2, enemy_horror=1,
        traits=["humanoid", "cultist"],
        keywords=["hunter"],
    )
    for ed in [spectral_librarian, animated_tome, shadow_acolyte]:
        g.register_card_data(ed)

    # Also register encounter enemy data
    animated_tome_enc = CardData(
        id="animated_tome_enc", name="Animated Tome", name_cn="活化典籍",
        type=CardType.ENEMY,
        enemy_fight=3, enemy_health=2, enemy_evade=2,
        enemy_damage=1, enemy_horror=1,
        traits=["monster"],
    )
    g.register_card_data(animated_tome_enc)

    # --- Player Cards ---
    cards_data = [
        CardData(
            id="magnifying_glass_lv0", name="Magnifying Glass", name_cn="放大镜",
            type=CardType.ASSET, card_class=PlayerClass.SEEKER, cost=1,
            slots=[SlotType.HAND], traits=["item", "tool"],
            skill_icons={"intellect": 1},
            text="调查时+1智力。",
        ),
        CardData(
            id="old_book_of_lore_lv0", name="Old Book of Lore", name_cn="古老学识之书",
            type=CardType.ASSET, card_class=PlayerClass.SEEKER, cost=3,
            slots=[SlotType.HAND], traits=["item", "tome"],
            skill_icons={"intellect": 1},
            text="消耗：查看牌库顶3张，选1张加入手牌。",
        ),
        CardData(
            id="medical_texts_lv0", name="Medical Texts", name_cn="医学典籍",
            type=CardType.ASSET, card_class=PlayerClass.SEEKER, cost=2,
            slots=[SlotType.HAND], traits=["item", "tome"],
            skill_icons={"willpower": 1},
            text="消耗：检定智力(2)，成功治疗1伤害。",
        ),
        CardData(
            id="encyclopedia_lv2", name="Encyclopedia", name_cn="百科��书",
            type=CardType.ASSET, card_class=PlayerClass.SEEKER, cost=2, level=2,
            slots=[SlotType.HAND], traits=["item", "tome"],
            skill_icons={"wild": 1},
            text="消耗：一名调查员一项技能+2直到阶段结束。",
        ),
        CardData(
            id="daisys_tote_bag", name="Daisy's Tote Bag", name_cn="黛西的手提包",
            type=CardType.ASSET, card_class=PlayerClass.SEEKER, cost=2,
            traits=["item"],
            skill_icons={"willpower": 1, "intellect": 1, "wild": 1},
            text="你可以额外装备2个手部栏位的典籍。",
            unique=True,
        ),
        CardData(
            id="the_necronomicon", name="The Necronomicon", name_cn="死灵之书",
            type=CardType.ASSET, card_class=PlayerClass.NEUTRAL, cost=None,
            traits=["item", "tome"],
            text="揭示—放入威胁区，上面放3恐惧。自由行动：移除1恐惧到自身。",
            unique=True,
        ),
        CardData(
            id="working_a_hunch_lv0", name="Working a Hunch", name_cn="灵光一闪",
            type=CardType.EVENT, card_class=PlayerClass.SEEKER, cost=2,
            skill_icons={"intellect": 2},
            text="发现当前地点1条线索（无需检定）。",
            fast=True,
        ),
        CardData(
            id="deduction_lv0", name="Deduction", name_cn="推理",
            type=CardType.SKILL, card_class=PlayerClass.SEEKER, cost=None,
            skill_icons={"intellect": 1},
            traits=["practiced"],
            text="投入到调查检定。成功时额外发现1条线索。",
        ),
        CardData(
            id="perception_lv0", name="Perception", name_cn="感知",
            type=CardType.SKILL, card_class=PlayerClass.NEUTRAL, cost=None,
            skill_icons={"intellect": 1},
            traits=["practiced"],
            text="成功时抽1张牌。",
        ),
        CardData(
            id="dr_milan_christopher_lv0", name="Dr. Milan Christopher",
            name_cn="米兰·克里斯托弗博士",
            type=CardType.ASSET, card_class=PlayerClass.SEEKER, cost=4,
            slots=[SlotType.ALLY], traits=["ally", "miskatonic"],
            skill_icons={"intellect": 1},
            text="+1智力。调查成功时获得1资源。",
            unique=True,
            health=1, sanity=2,
        ),
        CardData(
            id="research_librarian_lv0", name="Research Librarian",
            name_cn="研究图书管理员",
            type=CardType.ASSET, card_class=PlayerClass.SEEKER, cost=1,
            slots=[SlotType.ALLY], traits=["ally", "miskatonic"],
            skill_icons={"agility": 1},
            text="入场时从牌组检索1张典籍加入手牌。",
            health=1, sanity=1,
        ),
        CardData(
            id="hyperawareness_lv0", name="Hyperawareness", name_cn="高度警觉",
            type=CardType.ASSET, card_class=PlayerClass.SEEKER, cost=2,
            traits=["talent"],
            skill_icons={"intellect": 1, "agility": 1},
            text="花费1资源：+1智力或+1敏捷（本次检定）。",
        ),
        CardData(
            id="guts_lv0", name="Guts", name_cn="勇气",
            type=CardType.SKILL, card_class=PlayerClass.NEUTRAL, cost=None,
            skill_icons={"willpower": 2},
            traits=["innate"],
            text="成功时抽1张牌。",
        ),
        CardData(
            id="unexpected_courage_lv0", name="Unexpected Courage",
            name_cn="意外勇气",
            type=CardType.SKILL, card_class=PlayerClass.NEUTRAL, cost=None,
            skill_icons={"wild": 2},
            traits=["innate"],
            text="万能技能卡，可投入任何检定。",
        ),
        CardData(
            id="manual_dexterity_lv0", name="Manual Dexterity", name_cn="灵巧",
            type=CardType.SKILL, card_class=PlayerClass.NEUTRAL, cost=None,
            skill_icons={"agility": 2},
            traits=["innate"],
            text="成功时抽1张牌。",
        ),
        CardData(
            id="emergency_cache_lv0", name="Emergency Cache", name_cn="应急储备",
            type=CardType.EVENT, card_class=PlayerClass.NEUTRAL, cost=0,
            traits=["supply"],
            text="获得3资源。",
        ),
        CardData(
            id="knife_lv0", name="Knife", name_cn="小刀",
            type=CardType.ASSET, card_class=PlayerClass.NEUTRAL, cost=1,
            slots=[SlotType.HAND], traits=["item", "weapon", "melee"],
            skill_icons={"combat": 1},
            text="+1战斗。",
        ),
    ]
    for cd in cards_data:
        g.register_card_data(cd)

    # Register card implementations
    impl_classes = [
        DaisyWalker, DaisysToteBag, TheNecronomicon,
        MagnifyingGlass, Deduction, DrMilanChristopher,
        WorkingAHunch, OldBookOfLore, Knife, Guts,
        Perception, ManualDexterity, UnexpectedCourage,
        EmergencyCache, Hyperawareness, ResearchLibrarian,
        Encyclopedia, MedicalTexts,
    ]
    for cls in impl_classes:
        g.card_registry.register_class(cls)

    # Build 30-card deck (29 + 1 Necronomicon weakness)
    deck = (
        ["old_book_of_lore_lv0"] * 2
        + ["medical_texts_lv0"] * 2
        + ["encyclopedia_lv2"] * 1
        + ["daisys_tote_bag"] * 1
        + ["magnifying_glass_lv0"] * 2
        + ["working_a_hunch_lv0"] * 2
        + ["deduction_lv0"] * 2
        + ["perception_lv0"] * 2
        + ["guts_lv0"] * 2
        + ["unexpected_courage_lv0"] * 2
        + ["manual_dexterity_lv0"] * 2
        + ["emergency_cache_lv0"] * 2
        + ["knife_lv0"] * 2
        + ["dr_milan_christopher_lv0"] * 2
        + ["research_librarian_lv0"] * 1
        + ["hyperawareness_lv0"] * 2
        + ["the_necronomicon"] * 1  # weakness
    )
    random.shuffle(deck)

    # Add investigator and locations
    g.add_investigator("player", inv_card, deck=deck, starting_location="reading_room")
    g.add_location("reading_room", reading_room, clues=3)
    g.add_location("restricted_section", restricted_section, clues=4)
    g.add_location("archive", archive, clues=2)

    # Agenda (doom threshold = 8)
    g.state.scenario.agenda_deck = ["agenda_1"]
    g.state.scenario.doom_threshold = 8

    # Encounter deck (12 cards)
    encounter_ids = (
        ["whispering_voices"] * 2
        + ["grasping_tentacles"] * 2
        + ["ancient_evils"] * 2
        + ["forbidden_knowledge_enc"] * 2
        + ["animated_tome_enc"] * 2
    )
    # NOTE: only 10 unique encounter cards in plan (missing 2). Use 12 by adding 2 more
    encounter_ids += ["whispering_voices", "grasping_tentacles"]
    random.shuffle(encounter_ids)
    g.state.scenario.encounter_deck = encounter_ids

    # Spawn Spectral Librarian at Restricted Section (not engaged)
    spectral_inst = CardInstance(
        instance_id="spectral_librarian_1",
        card_id="spectral_librarian",
        owner_id="scenario",
        controller_id="scenario",
    )
    g.state.cards_in_play["spectral_librarian_1"] = spectral_inst
    g.state.get_location("restricted_section").enemies.append("spectral_librarian_1")

    # Setup: draw 5, 5 resources
    g.setup()

    # Register global listeners
    cache_impl = EmergencyCache("cache_listener")
    cache_impl.register(g.event_bus, "cache_listener")

    # Register Daisy Walker investigator ability
    daisy_impl = DaisyWalker("daisy_ability")
    daisy_impl.register(g.event_bus, "daisy_ability")

    # Register The Necronomicon listener (for revelation when drawn)
    necro_impl = TheNecronomicon("necro_listener")
    necro_impl.register(g.event_bus, "necro_listener")
    necronomicon_instance = necro_impl

    # Register Working a Hunch
    hunch_impl = WorkingAHunch("hunch_listener")
    hunch_impl.register(g.event_bus, "hunch_listener")

    # Register Deduction
    deduction_impl = Deduction("deduction_listener")
    deduction_impl.register(g.event_bus, "deduction_listener")

    # Register Dr. Milan Christopher
    milan_impl = DrMilanChristopher("milan_listener")
    milan_impl.register(g.event_bus, "milan_listener")

    # Register MagnifyingGlass
    mag_impl = MagnifyingGlass("mag_listener")
    mag_impl.register(g.event_bus, "mag_listener")

    # Register Knife
    knife_impl = Knife("knife_listener")
    knife_impl.register(g.event_bus, "knife_listener")

    # Register Guts, Perception, ManualDexterity, UnexpectedCourage
    for cls, name in [(Guts, "guts"), (Perception, "perception"),
                      (ManualDexterity, "mandex"), (UnexpectedCourage, "ucourage")]:
        impl = cls(f"{name}_listener")
        impl.register(g.event_bus, f"{name}_listener")

    # Fire INVESTIGATION_PHASE_BEGINS so Daisy gets +1 action
    g.state.scenario.current_phase = Phase.INVESTIGATION
    g.state.scenario.round_number = 1
    inv = g.state.get_investigator("player")
    inv.actions_remaining = 3

    # Manually grant Daisy's +1 action
    inv.actions_remaining = 4

    action_log.append("=== 失落知识的图书馆 ===")
    action_log.append("黛西在米斯卡托尼克大学图书馆深夜研究，")
    action_log.append("发现古老典籍隐藏着危险知识...")
    action_log.append("目标：收集7条线索并返回阅览室")
    action_log.append(f"密谋：毁灭达到{g.state.scenario.doom_threshold}时游戏失败")
    action_log.append("阅览室(3线索) ←→ 禁区(4线索) ←→ 档案室(2线索)")
    action_log.append("幽灵馆员(猎人)在禁区巡逻")
    action_log.append(f"=== 第1轮 调查阶段（{inv.actions_remaining}行动）===")
    return g


# ============================================================
# State serialization
# ============================================================

def serialize_state(g: Game) -> dict:
    inv = g.state.get_investigator("player")
    current_loc = g.state.get_location(inv.location_id)

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
                "is_tome": "tome" in cd.traits,
                "is_fast": cd.fast,
            })

    play_area = []
    for inst_id in inv.play_area:
        ci = g.state.get_card_instance(inst_id)
        if ci:
            cd = g.state.get_card_data(ci.card_id)
            is_ally = cd and ("ally" in cd.traits or SlotType.ALLY in cd.slots)
            entry = {
                "instance_id": ci.instance_id,
                "id": ci.card_id,
                "name": cd.name if cd else ci.card_id,
                "name_cn": cd.name_cn if cd else "",
                "exhausted": ci.exhausted,
                "uses": ci.uses,
                "slots": [s.value for s in ci.slot_used],
                "traits": cd.traits if cd else [],
                "is_tome": cd and "tome" in cd.traits,
                "is_ally": bool(is_ally),
            }
            if is_ally:
                entry["health"] = cd.health
                entry["sanity"] = cd.sanity
                entry["damage"] = ci.damage
                entry["horror"] = ci.horror
                entry["remaining_health"] = (cd.health - ci.damage) if cd.health is not None else None
                entry["remaining_sanity"] = (cd.sanity - ci.horror) if cd.sanity is not None else None
            play_area.append(entry)

    # Threat area (Necronomicon + engaged enemies are separate)
    threat_area_cards = []
    enemies = []
    for inst_id in inv.threat_area:
        ci = g.state.get_card_instance(inst_id)
        if ci:
            cd = g.state.get_card_data(ci.card_id)
            if cd and cd.type == CardType.ENEMY:
                enemies.append(_enemy_dict(ci, cd, engaged=True))
            else:
                # Non-enemy threat area card (Necronomicon)
                threat_area_cards.append({
                    "instance_id": ci.instance_id,
                    "id": ci.card_id,
                    "name": cd.name if cd else ci.card_id,
                    "name_cn": cd.name_cn if cd else "",
                    "uses": ci.uses,
                    "traits": cd.traits if cd else [],
                })

    if current_loc:
        for inst_id in current_loc.enemies:
            ci = g.state.get_card_instance(inst_id)
            if ci:
                cd = g.state.get_card_data(ci.card_id)
                enemies.append(_enemy_dict(ci, cd, engaged=False))

    scenario = g.state.scenario
    return {
        "investigator": {
            "name": "黛西·沃克",
            "name_en": "Daisy Walker",
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
            "skills": {
                "willpower": 3, "intellect": 5, "combat": 2, "agility": 2,
            },
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
        "threat_area": threat_area_cards,
        "enemies": enemies,
        "phase": scenario.current_phase.name,
        "round": scenario.round_number,
        "doom": scenario.doom_on_agenda,
        "doom_threshold": scenario.doom_threshold,
        "encounter_deck_count": len(scenario.encounter_deck),
        "total_clues_needed": 7,
        "win_location": "reading_room",
        "chaos_bag": {
            "tokens": {t.value: c for t, c in Counter(g.chaos_bag.tokens).items()},
            "sealed": {t.value: c for t, c in Counter(g.chaos_bag.sealed).items()},
            "total": len(g.chaos_bag.tokens),
        },
        "ally_soak_targets": g.damage_engine.get_ally_soak_targets("player"),
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
        "keywords": cd.keywords if cd else [],
    }


# ============================================================
# Encounter card resolution
# ============================================================

def resolve_encounter_card(card_id: str) -> str:
    global game, action_log
    inv = game.state.get_investigator("player")
    enc = ENCOUNTER_CARDS.get(card_id)
    if not enc:
        return f"未知遭遇卡: {card_id}"

    action_log.append(f"📜 遭遇卡: {enc['name_cn']} ({enc['name']})")
    action_log.append(f"   {enc['text']}")

    if enc["type"] == "enemy":
        inst_id = game.state.next_instance_id()
        enemy_inst = CardInstance(
            instance_id=inst_id, card_id=card_id,
            owner_id="scenario", controller_id="scenario",
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
        if enc.get("doom_check_immediate", True):
            check_agenda()
        return f"+{enc['fail_amount']} doom"

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
            elif effect == "damage_and_discard":
                game.damage_engine.deal_damage("player", damage=enc["fail_amount"])
                if inv.hand:
                    discarded = inv.hand.pop(random.randrange(len(inv.hand)))
                    inv.discard.append(discarded)
                    cd = game.state.get_card_data(discarded)
                    dname = cd.name_cn if cd else discarded
                    action_log.append(f"💥 受到{enc['fail_amount']}点伤害，弃掉{dname}")
                else:
                    action_log.append(f"💥 受到{enc['fail_amount']}点伤害")
            elif effect == "horror_and_doom":
                game.damage_engine.deal_damage("player", horror=enc["fail_amount"])
                game.state.scenario.doom_on_agenda += enc["fail_amount"]
                action_log.append(f"😱 受到{enc['fail_amount']}点恐惧，密谋+{enc['fail_amount']}毁灭 (当前: {game.state.scenario.doom_on_agenda}/{game.state.scenario.doom_threshold})")
                if enc.get("doom_check_immediate", True):
                    check_agenda()
            return f"检定失败: {effect}"

    return "resolved"


def check_agenda():
    global game_over
    scenario = game.state.scenario
    if scenario.doom_on_agenda >= scenario.doom_threshold:
        game_over = {
            "type": "lose",
            "message": f"毁灭标记达到{scenario.doom_threshold}！黑暗力量苏醒，图书馆被吞噬..."
        }
        action_log.append(f"💀💀💀 密谋推进！毁灭达到{scenario.doom_threshold}！游戏失败！")


def check_win():
    global game_over
    inv = game.state.get_investigator("player")
    if inv.clues >= 7 and inv.location_id == "reading_room":
        game_over = {
            "type": "win",
            "message": f"你收集了{inv.clues}条线索并安全返回阅览室！古老知识已被保护。"
        }
        action_log.append(f"🎉🎉🎉 收集了{inv.clues}条线索并返回阅览室！调查成功！")


# ============================================================
# Action handling
# ============================================================

def handle_action(data: dict) -> dict:
    global game, action_log, game_over
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
                # Find first enemy in threat area
                for tid in inv.threat_area:
                    ci = game.state.get_card_instance(tid)
                    if ci:
                        cd = game.state.get_card_data(ci.card_id)
                        if cd and cd.type == CardType.ENEMY:
                            enemy_id = tid
                            break
            if not enemy_id and location and location.enemies:
                enemy_id = location.enemies[0]
            if not enemy_id:
                return {"success": False, "message": "没有可攻击的敌人"}

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
        if not enemy_id:
            for tid in inv.threat_area:
                ci = game.state.get_card_instance(tid)
                if ci:
                    cd = game.state.get_card_data(ci.card_id)
                    if cd and cd.type == CardType.ENEMY:
                        enemy_id = tid
                        break
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
            gained = inv.clues - old_clues
            if gained > 0:
                action_log.append(f"🔍 调查成功！发现{gained}条线索 (共{inv.clues}条)")
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
                # Check if Necronomicon was drawn (it auto-moves to threat area)
                check_necronomicon_drawn()
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
        old_clues = inv.clues
        ok = game.action_resolver.perform_action("player", Action.PLAY, card_id=card_id)
        if ok:
            action_log.append(f"🎴 打出: {cd.name_cn} ({cd.name})")
            if inv.clues > old_clues:
                action_log.append(f"🔍 发现{inv.clues - old_clues}条线索！(共{inv.clues}条)")
                check_win()
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
            # Check win after moving
            check_win()
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

    elif action_name == "ACTIVATE_NECRONOMICON":
        # Special action: activate The Necronomicon (free action, no action cost)
        result = handle_activate_necronomicon()

    elif action_name == "ACTIVATE_TOME":
        # Activate a tome ability (uses Daisy's bonus action or regular action)
        instance_id = data.get("instance_id")
        result = handle_activate_tome(instance_id)

    elif action_name == "ASSIGN_DAMAGE":
        # Manually assign damage/horror to allies (for enemy attacks, etc.)
        damage_map = data.get("damage_assignment", {})  # {instance_id: amount}
        horror_map = data.get("horror_assignment", {})
        total_damage = data.get("total_damage", 0)
        total_horror = data.get("total_horror", 0)
        source = data.get("source")
        game.damage_engine.deal_damage(
            "player", damage=total_damage, horror=total_horror,
            source=source,
            damage_assignment=damage_map,
            horror_assignment=horror_map,
        )
        action_log.append(f"💔 分配伤害: {total_damage}伤害/{total_horror}恐惧")
        for inst_id, amt in damage_map.items():
            ci = game.state.get_card_instance(inst_id)
            if ci:
                cd = game.state.get_card_data(ci.card_id)
                name = cd.name_cn if cd else inst_id
                action_log.append(f"   {name}承受{amt}点伤害")
        for inst_id, amt in horror_map.items():
            ci = game.state.get_card_instance(inst_id)
            if ci:
                cd = game.state.get_card_data(ci.card_id)
                name = cd.name_cn if cd else inst_id
                action_log.append(f"   {name}承受{amt}点恐惧")
        if inv.is_defeated:
            game_over = {"type": "lose", "message": "黛西被击败了！"}
            action_log.append("💀 黛西被击败！游戏结束！")
        result = {"success": True, "message": "伤害已分配"}

    return result


def check_necronomicon_drawn():
    """Check if Necronomicon ended up in hand and handle revelation."""
    inv = game.state.get_investigator("player")
    if "the_necronomicon" in inv.hand:
        inv.hand.remove("the_necronomicon")
        inst_id = game.state.next_instance_id()
        ci = CardInstance(
            instance_id=inst_id,
            card_id="the_necronomicon",
            owner_id="player",
            controller_id="player",
        )
        ci.uses = {"horror": 3}
        game.state.cards_in_play[inst_id] = ci
        inv.threat_area.append(inst_id)
        action_log.append(f"📕 死灵之书揭示！放入威胁区，上面放置3个恐惧标记")
        action_log.append(f"   自由行动：点击激活可将1恐惧移到黛西身上")


def handle_activate_necronomicon() -> dict:
    """Activate Necronomicon: move 1 horror token to investigator (free action)."""
    inv = game.state.get_investigator("player")
    necro_inst = None
    necro_inst_id = None
    for inst_id in inv.threat_area:
        ci = game.state.get_card_instance(inst_id)
        if ci and ci.card_id == "the_necronomicon":
            necro_inst = ci
            necro_inst_id = inst_id
            break

    if not necro_inst:
        return {"success": False, "message": "威胁区没有死灵之书"}

    horror_left = necro_inst.uses.get("horror", 0)
    if horror_left <= 0:
        return {"success": False, "message": "死灵之书上没有恐惧标记了"}

    necro_inst.uses["horror"] -= 1
    inv.horror += 1
    remaining = necro_inst.uses["horror"]
    action_log.append(f"📕 激活死灵之书：移除1恐惧到黛西 (剩余{remaining}恐惧)")

    if remaining <= 0:
        inv.threat_area.remove(necro_inst_id)
        inv.discard.append("the_necronomicon")
        del game.state.cards_in_play[necro_inst_id]
        action_log.append(f"📕 死灵之书上的恐惧已清除，弃入弃牌堆")

    if inv.is_defeated:
        global game_over
        game_over = {"type": "lose", "message": "黛西被恐惧击垮了..."}
        action_log.append("💀 黛西被击败！游戏结束！")

    return {"success": True, "message": action_log[-1]}


def handle_activate_tome(instance_id: str) -> dict:
    """Activate a tome ability (exhaust it, trigger effect)."""
    inv = game.state.get_investigator("player")
    if not instance_id:
        return {"success": False, "message": "未指定典籍"}

    ci = game.state.get_card_instance(instance_id)
    if not ci:
        return {"success": False, "message": "找不到该卡牌"}
    if ci.exhausted:
        return {"success": False, "message": "该典籍已消耗"}

    cd = game.state.get_card_data(ci.card_id)
    if not cd or "tome" not in cd.traits:
        return {"success": False, "message": "该卡牌不是典籍"}

    # Costs 1 action (can be Daisy's bonus tome action)
    if inv.actions_remaining <= 0:
        return {"success": False, "message": "没有剩余行动点"}
    inv.actions_remaining -= 1

    ci.exhausted = True

    # Handle specific tome effects
    if ci.card_id == "old_book_of_lore_lv0":
        if inv.deck:
            drawn_card = inv.deck.pop(0)
            inv.hand.append(drawn_card)
            drawn_cd = game.state.get_card_data(drawn_card)
            name = drawn_cd.name_cn if drawn_cd else drawn_card
            action_log.append(f"📖 激活{cd.name_cn}：从牌库顶抽到{name}")
            check_necronomicon_drawn()
        else:
            action_log.append(f"📖 激活{cd.name_cn}：牌库已空")
    elif ci.card_id == "medical_texts_lv0":
        # Simplified: heal 1 damage if any
        if inv.damage > 0:
            inv.damage -= 1
            action_log.append(f"📖 激活{cd.name_cn}：治疗1点伤害 (HP:{inv.remaining_health}/{inv.health})")
        else:
            action_log.append(f"📖 激活{cd.name_cn}：没有伤害需要治疗")
    elif ci.card_id == "encyclopedia_lv2":
        # Simplified: +2 intellect for this phase
        action_log.append(f"📖 激活{cd.name_cn}：智力+2直到阶段结束")
    else:
        action_log.append(f"📖 激活{cd.name_cn}")

    return {"success": True, "message": action_log[-1]}


# ============================================================
# End turn
# ============================================================

def handle_end_turn() -> dict:
    global game, action_log, game_over
    inv = game.state.get_investigator("player")

    if inv.is_defeated or game_over:
        return {"message": "游戏已结束"}

    # === Enemy Phase ===
    action_log.append("--- 敌人阶段 ---")
    old_damage = inv.damage
    old_horror = inv.horror

    # Hunter enemies move toward investigator
    handle_hunter_enemies()

    game.enemy_phase.resolve()

    if inv.damage > old_damage or inv.horror > old_horror:
        action_log.append(f"👹 敌人攻击！受到{inv.damage - old_damage}伤害/{inv.horror - old_horror}恐惧 (HP:{inv.remaining_health}/{inv.health} SAN:{inv.remaining_sanity}/{inv.sanity})")
    else:
        action_log.append("敌人未攻击（已消耗或无交战敌人）")

    if inv.is_defeated:
        action_log.append("💀 黛西被击败！游戏结束！")
        game_over = {"type": "lose", "message": "黛西被击败了！"}
        return {"message": "调查员被击败！"}

    # === Upkeep Phase ===
    action_log.append("--- 刷新阶段 ---")
    game.upkeep_phase.resolve()
    action_log.append(f"♻️ 刷新：就绪所有卡牌，抽1牌，+1资源 (资源:{inv.resources}，手牌:{len(inv.hand)})")
    check_necronomicon_drawn()

    # === New Round ===
    game.state.scenario.round_number += 1

    # === Mythos Phase ===
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

        # Check if encounter card caused game over (e.g. Ancient Evils doom)
        if game_over:
            return {"message": game_over["message"]}

        if inv.is_defeated:
            action_log.append("💀 黛西被击败！游戏结束！")
            game_over = {"type": "lose", "message": "黛西被遭遇卡击败！"}
            return {"message": "调查员被击败！"}
    else:
        scenario.encounter_deck = list(scenario.encounter_discard)
        random.shuffle(scenario.encounter_deck)
        scenario.encounter_discard.clear()
        action_log.append("♻️ 遭遇弃牌堆洗回")

    # Begin new investigation phase with Daisy's +1 action
    inv.actions_remaining = 4  # 3 base + 1 Daisy bonus
    inv.has_taken_turn = False
    game.state.scenario.current_phase = Phase.INVESTIGATION

    action_log.append(f"=== 第{game.state.scenario.round_number}轮 调查阶段（{inv.actions_remaining}行动）===")
    return {"message": f"进入第{game.state.scenario.round_number}轮"}


def handle_hunter_enemies():
    """Move hunter enemies one location toward the investigator."""
    inv = game.state.get_investigator("player")
    inv_loc_id = inv.location_id

    # Check each location for hunter enemies
    for loc_id, loc in list(game.state.locations.items()):
        if loc_id == inv_loc_id:
            continue
        for enemy_id in list(loc.enemies):
            ci = game.state.get_card_instance(enemy_id)
            if not ci:
                continue
            cd = game.state.get_card_data(ci.card_id)
            if not cd or "hunter" not in (cd.keywords or []):
                continue
            # Find path toward investigator
            next_loc = find_next_location_toward(loc_id, inv_loc_id)
            if next_loc:
                loc.enemies.remove(enemy_id)
                if next_loc == inv_loc_id:
                    # Arrives at investigator's location — engage
                    inv.threat_area.append(enemy_id)
                    action_log.append(f"🏃 {cd.name_cn}(猎人)追踪到{game.state.get_location(inv_loc_id).card_data.name_cn}并与你交战！")
                else:
                    game.state.get_location(next_loc).enemies.append(enemy_id)
                    action_log.append(f"🏃 {cd.name_cn}(猎人)向你移动到{game.state.get_location(next_loc).card_data.name_cn}")


def find_next_location_toward(from_loc: str, to_loc: str) -> str | None:
    """Simple BFS to find next location on shortest path."""
    if from_loc == to_loc:
        return None
    from collections import deque
    visited = {from_loc}
    queue = deque([(from_loc, [from_loc])])
    while queue:
        current, path = queue.popleft()
        loc = game.state.get_location(current)
        if not loc:
            continue
        for neighbor in loc.connections:
            if neighbor == to_loc:
                return path[1] if len(path) > 1 else neighbor
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, path + [neighbor]))
    return None


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
        html_path = Path(__file__).parent / "daisy.html"
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html_path.read_bytes())

    def log_message(self, format, *args):
        pass


def main():
    global game
    game = create_game()
    port = 8909
    server = HTTPServer(("0.0.0.0", port), GameHandler)
    print(f"Arkham Horror LCG — 失落知识的图书馆 (Daisy Walker)")
    print(f"http://localhost:{port}")
    print(f"黛西·沃克 | HP:5 SAN:9 | 智力5 战斗2")
    print(f"目标: 收集7线索 + 返回阅览室 | 毁灭阈值: 8")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")


if __name__ == "__main__":
    main()
