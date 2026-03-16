#!/usr/bin/env python3
"""Fetch Dunwich Legacy cards from ArkhamDB API and generate project-format JSON.

Usage:
    python3 skills/import-campaign/scripts/fetch_cards.py

Outputs:
    data/encounter_cards/dunwich_legacy.json   — encounter/scenario cards (~221)
    data/player_cards/_import/dwl_players.json  — player cards for manual split
    data/investigators/_import/dwl_investigators.json — investigator data
"""

import json
import re
import time
import urllib.request
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent

# ArkhamDB API endpoints
EN_API = "https://arkhamdb.com/api/public/cards/{pack}"
ZH_API = "https://zh.arkhamdb.com/api/public/cards/{pack}"


def fetch_json(url: str) -> list[dict]:
    """Fetch JSON from URL with retry."""
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "ArkhamImporter/1.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            print(f"  Attempt {attempt+1} failed for {url}: {e}")
            time.sleep(2)
    raise RuntimeError(f"Failed to fetch {url}")


def code_to_id(name: str) -> str:
    """Convert card name to snake_case ID."""
    s = name.lower().strip()
    s = s.replace('"', '').replace("'", "").replace(".", "").replace(",", "")
    s = s.replace("(", "").replace(")", "").replace(":", "").replace("!", "")
    s = s.replace("?", "").replace("-", " ").replace("/", " ")
    s = re.sub(r"\s+", "_", s.strip())
    s = re.sub(r"_+", "_", s).strip("_")
    return s


def merge_en_zh(en_cards: list[dict], zh_cards: list[dict]) -> list[dict]:
    """Merge English and Chinese card data by code."""
    zh_map = {c["code"]: c for c in zh_cards}
    merged = []
    for en in en_cards:
        zh = zh_map.get(en["code"], {})
        card = dict(en)
        card["name_cn"] = zh.get("name", "")
        card["text_cn"] = zh.get("text", "")
        card["subname_cn"] = zh.get("subname", "")
        card["traits_cn"] = zh.get("traits", "")
        merged.append(card)
    return merged


def classify_type(type_code: str) -> str:
    """Map ArkhamDB type_code to project type."""
    mapping = {
        "investigator": "investigator",
        "asset": "asset",
        "event": "event",
        "skill": "skill",
        "treachery": "treachery",
        "enemy": "enemy",
        "location": "location",
        "scenario": "scenario",
        "act": "act",
        "agenda": "agenda",
        "story": "story",
    }
    return mapping.get(type_code, type_code)


def parse_traits(traits_str: str | None) -> list[str]:
    """Parse traits string like 'Humanoid. Criminal.' into list."""
    if not traits_str:
        return []
    return [t.strip().lower() for t in traits_str.replace(".", "").split(".") if t.strip()]


def parse_traits_dotted(traits_str: str | None) -> list[str]:
    """Parse traits from ArkhamDB format."""
    if not traits_str:
        return []
    # "Humanoid. Criminal. Elite." -> ["humanoid", "criminal", "elite"]
    parts = [t.strip() for t in traits_str.split(".") if t.strip()]
    return [p.lower() for p in parts]


def card_to_encounter_format(card: dict) -> dict:
    """Convert API card to encounter_cards DB format (matching core_set.json)."""
    card_id = code_to_id(card.get("name", card["code"]))
    card_type = classify_type(card.get("type_code", ""))

    stats = {}
    # Enemy stats
    if card.get("enemy_fight") is not None:
        stats["fight"] = card["enemy_fight"]
    if card.get("enemy_evade") is not None:
        stats["evade"] = card["enemy_evade"]
    if card.get("health") is not None and card_type == "enemy":
        stats["health"] = card["health"]
    if card.get("enemy_damage") is not None:
        stats["damage"] = card["enemy_damage"]
    if card.get("enemy_horror") is not None:
        stats["horror"] = card["enemy_horror"]
    # Location stats
    if card.get("shroud") is not None:
        stats["shroud"] = card["shroud"]
    if card.get("clues") is not None:
        stats["clues"] = card["clues"]
    if card.get("clues_fixed") is not None:
        stats["clues_fixed"] = card["clues_fixed"]
    # Agenda/Act stats
    if card.get("doom") is not None:
        stats["doom"] = card["doom"]
    if card.get("victory") is not None:
        stats["victory"] = card["victory"]
    # Asset stats (for story assets)
    if card.get("cost") is not None:
        stats["cost"] = card["cost"]
    if card.get("health") is not None and card_type in ("asset",):
        stats["health"] = card["health"]
    if card.get("sanity") is not None:
        stats["sanity"] = card["sanity"]

    return {
        "id": card_id,
        "arkhamdb_code": card["code"],
        "encounter_code": card.get("encounter_code", ""),
        "encounter_name": card.get("encounter_name", ""),
        "type": card_type,
        "name": card.get("name", ""),
        "name_cn": card.get("name_cn", ""),
        "traits": parse_traits_dotted(card.get("traits")),
        "text": card.get("text", ""),
        "text_cn": card.get("text_cn", ""),
        "stats": stats,
        "meta": {
            "subname": card.get("subname", ""),
            "subname_cn": card.get("subname_cn", ""),
            "position": card.get("position", 0),
            "quantity": card.get("quantity", 1),
        },
    }


def card_to_player_format(card: dict) -> dict:
    """Convert API card to player card format."""
    card_id = code_to_id(card.get("name", card["code"]))
    xp = card.get("xp", 0) or 0
    if xp > 0:
        card_id = f"{card_id}_lv{xp}"
    elif card.get("type_code") not in ("investigator",):
        card_id = f"{card_id}_lv0"

    skill_icons = {}
    for skill in ("willpower", "intellect", "combat", "agility", "wild"):
        val = card.get(f"skill_{skill}", 0) or 0
        if val > 0:
            skill_icons[skill] = val

    slots = []
    slot_str = card.get("slot", "")
    if slot_str:
        slot_map = {
            "Hand": "hand", "Hand x2": "hand",
            "Accessory": "accessory", "Ally": "ally",
            "Arcane": "arcane", "Body": "body",
        }
        slots = [slot_map.get(slot_str, slot_str.lower())]

    result = {
        "id": card_id,
        "arkhamdb_code": card["code"],
        "name": card.get("name", ""),
        "name_cn": card.get("name_cn", ""),
        "class": card.get("faction_code", "neutral"),
        "type": card.get("type_code", ""),
        "cost": card.get("cost"),
        "level": xp,
        "traits": parse_traits_dotted(card.get("traits")),
        "skill_icons": skill_icons,
        "slots": slots,
        "text": card.get("text", ""),
        "text_cn": card.get("text_cn", ""),
        "health": card.get("health"),
        "sanity": card.get("sanity"),
        "unique": card.get("is_unique", False),
        "pack": "dunwich_legacy",
    }

    # Weakness info
    if card.get("subtype_code") == "weakness":
        result["subtype"] = "weakness"
    if card.get("subtype_code") == "basicweakness":
        result["subtype"] = "basic_weakness"

    return result


def card_to_investigator_format(card: dict) -> dict:
    """Convert API investigator card to investigator format."""
    card_id = code_to_id(card.get("name", card["code"]))

    skills = {}
    for skill in ("willpower", "intellect", "combat", "agility"):
        skills[skill] = card.get(f"skill_{skill}", 0) or 0

    faction = card.get("faction_code", "neutral")

    # Parse deck requirements from text (simplified)
    deck_req = {
        "size": 30,
        "cards": {
            faction: {"min_level": 0, "max_level": 5},
            "neutral": {"min_level": 0, "max_level": 5},
        }
    }

    return {
        "id": card_id,
        "arkhamdb_code": card["code"],
        "name": card.get("name", ""),
        "name_cn": card.get("name_cn", ""),
        "title": card.get("subname", ""),
        "title_cn": card.get("subname_cn", ""),
        "class": faction,
        "health": card.get("health", 5),
        "sanity": card.get("sanity", 5),
        "skills": skills,
        "ability": card.get("text", ""),
        "ability_cn": card.get("text_cn", ""),
        "elder_sign": "",
        "elder_sign_cn": "",
        "deck_requirements": deck_req,
        "signature_cards": [],
        "weakness": "",
        "flavor_text": card.get("flavor", ""),
        "pack": "dunwich_legacy",
    }


def main():
    print("Fetching Dunwich Legacy cards from ArkhamDB...")

    # Fetch encounter/campaign cards (dwlc)
    print("\n[1/4] Fetching EN encounter cards (dwlc)...")
    en_encounter = fetch_json(EN_API.format(pack="dwlc"))
    print(f"  Got {len(en_encounter)} EN cards")

    print("[2/4] Fetching ZH encounter cards (dwlc)...")
    time.sleep(1)
    zh_encounter = fetch_json(ZH_API.format(pack="dwlc"))
    print(f"  Got {len(zh_encounter)} ZH cards")

    encounter_merged = merge_en_zh(en_encounter, zh_encounter)

    # Fetch player cards (dwl)
    print("[3/4] Fetching EN player cards (dwl)...")
    time.sleep(1)
    en_player = fetch_json(EN_API.format(pack="dwl"))
    print(f"  Got {len(en_player)} EN cards")

    print("[4/4] Fetching ZH player cards (dwl)...")
    time.sleep(1)
    zh_player = fetch_json(ZH_API.format(pack="dwl"))
    print(f"  Got {len(zh_player)} ZH cards")

    player_merged = merge_en_zh(en_player, zh_player)

    # Process encounter cards — deduplicate IDs with _a/_b/_c suffixes
    encounter_cards = []
    id_counter: dict[str, int] = {}
    for card in encounter_merged:
        entry = card_to_encounter_format(card)
        base_id = entry["id"]
        if base_id in id_counter:
            id_counter[base_id] += 1
            suffix = chr(ord('a') + id_counter[base_id] - 1)  # b, c, d...
            entry["id"] = f"{base_id}_{suffix}"
        else:
            id_counter[base_id] = 1
            # First occurrence keeps base ID (will be renamed to _a if dupe found later)

    # Second pass: rename first occurrence to _a if it has duplicates
    first_ids = {}
    for entry in encounter_cards:
        pass  # need to rebuild
    encounter_cards = []
    id_counter = {}
    raw_entries = [card_to_encounter_format(card) for card in encounter_merged]
    from collections import Counter
    id_counts = Counter(e["id"] for e in raw_entries)
    seen: dict[str, int] = {}
    for entry in raw_entries:
        base_id = entry["id"]
        if id_counts[base_id] > 1:
            idx = seen.get(base_id, 0)
            suffix = chr(ord('a') + idx)
            entry["id"] = f"{base_id}_{suffix}"
            seen[base_id] = idx + 1
        encounter_cards.append(entry)

    encounter_db = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source": "https://arkhamdb.com/api/public/cards/dwlc + zh.arkhamdb.com",
        "code_range": [2040, 2333],
        "cards": encounter_cards,
    }

    out_enc = PROJECT_ROOT / "data" / "encounter_cards" / "dunwich_legacy.json"
    out_enc.write_text(json.dumps(encounter_db, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n✅ Wrote {len(encounter_cards)} encounter cards to {out_enc}")

    # Process player cards
    investigators = []
    player_cards = []
    for card in player_merged:
        if card.get("type_code") == "investigator":
            investigators.append(card_to_investigator_format(card))
        else:
            player_cards.append(card_to_player_format(card))

    # Write investigators
    inv_dir = PROJECT_ROOT / "data" / "investigators"
    for inv in investigators:
        inv_path = inv_dir / f"{inv['id']}.json"
        inv_path.write_text(json.dumps(inv, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"  ✅ Wrote investigator: {inv_path.name}")

    # Write player cards by class
    for pc in player_cards:
        pc_class = pc.get("class", "neutral")
        pc_dir = PROJECT_ROOT / "data" / "player_cards" / pc_class
        pc_dir.mkdir(parents=True, exist_ok=True)
        pc_path = pc_dir / f"{pc['id']}.json"
        pc_path.write_text(json.dumps(pc, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"  ✅ Wrote {len(player_cards)} player cards")
    print(f"  ✅ Wrote {len(investigators)} investigators")

    # Summary
    types = {}
    for c in encounter_cards:
        t = c["type"]
        types[t] = types.get(t, 0) + 1

    print(f"\n📊 Encounter card breakdown:")
    for t, count in sorted(types.items()):
        print(f"  {t}: {count}")

    # List encounter codes for scenario definition
    enc_codes = set()
    for c in encounter_cards:
        if c["encounter_code"]:
            enc_codes.add(c["encounter_code"])
    print(f"\n📋 Encounter codes ({len(enc_codes)}):")
    for code in sorted(enc_codes):
        cards_in_set = [c for c in encounter_cards if c["encounter_code"] == code]
        print(f"  {code}: {len(cards_in_set)} cards")


if __name__ == "__main__":
    main()
