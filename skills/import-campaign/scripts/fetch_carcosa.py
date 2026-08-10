#!/usr/bin/env python3
"""Fetch The Path to Carcosa cards from ArkhamDB API and generate project-format JSON.

Usage:
    python3 skills/import-campaign/scripts/fetch_carcosa.py

Outputs:
    data/encounter_cards/path_to_carcosa.json  — encounter/scenario cards (ptcc, ~241)
    data/player_cards/{class}/*.json           — player cards (ptcp, ~108)
    data/investigators/*.json                  — 6 investigators (deck rules需人工复核)
"""

import json
import re
import time
import urllib.request
from collections import Counter
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent

EN_API = "https://arkhamdb.com/api/public/cards/{pack}"
ZH_API = "https://zh.arkhamdb.com/api/public/cards/{pack}"

PLAYER_PACK = "ptcp"     # The Path to Carcosa investigator expansion (all player cards)
ENCOUNTER_PACK = "ptcc"  # The Path to Carcosa campaign expansion
PACK_ID = "path_to_carcosa"

# ArkhamDB uses-type → 项目约定键名（与 server/game_session.py 的特判一致用复数）
USES_KEY = {
    "charge": "charges", "supply": "supplies", "secret": "secrets",
    "ammo": "ammo", "offering": "offerings", "key": "keys", "doom": "doom",
}


def fetch_json(url: str) -> list[dict]:
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
    s = name.lower().strip()
    s = s.replace('"', '').replace("'", "").replace(".", "").replace(",", "")
    s = s.replace("(", "").replace(")", "").replace(":", "").replace("!", "")
    s = s.replace("?", "").replace("-", " ").replace("/", " ")
    s = re.sub(r"\s+", "_", s.strip())
    s = re.sub(r"_+", "_", s).strip("_")
    return s


def merge_en_zh(en_cards: list[dict], zh_cards: list[dict]) -> list[dict]:
    zh_map = {c["code"]: c for c in zh_cards}
    merged = []
    for en in en_cards:
        zh = zh_map.get(en["code"], {})
        card = dict(en)
        card["name_cn"] = zh.get("name", "")
        card["text_cn"] = zh.get("text", "")
        card["subname_cn"] = zh.get("subname", "")
        card["traits_cn"] = zh.get("traits", "")
        card["back_text_cn"] = zh.get("back_text", "")
        merged.append(card)
    return merged


def classify_type(type_code: str) -> str:
    mapping = {
        "investigator": "investigator", "asset": "asset", "event": "event",
        "skill": "skill", "treachery": "treachery", "enemy": "enemy",
        "location": "location", "scenario": "scenario", "act": "act",
        "agenda": "agenda", "story": "story",
    }
    return mapping.get(type_code, type_code)


def parse_traits_dotted(traits_str: str | None) -> list[str]:
    if not traits_str:
        return []
    return [p.strip().lower() for p in traits_str.split(".") if p.strip()]


def parse_uses(text: str | None) -> dict | None:
    """Parse 'Uses (4 ammo).' / 'Uses (3 charges)' from card text."""
    if not text:
        return None
    m = re.search(r"Uses \((\d+) (\w+)\)", text)
    if not m:
        return None
    n, kind = int(m.group(1)), m.group(2).lower()
    kind = USES_KEY.get(kind, kind + "s")
    return {kind: n}


def card_to_encounter_format(card: dict) -> dict:
    card_id = code_to_id(card.get("name", card["code"]))
    card_type = classify_type(card.get("type_code", ""))

    stats = {}
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
    if card.get("shroud") is not None:
        stats["shroud"] = card["shroud"]
    if card.get("clues") is not None:
        stats["clues"] = card["clues"]
    if card.get("clues_fixed") is not None:
        stats["clues_fixed"] = card["clues_fixed"]
    if card.get("doom") is not None:
        stats["doom"] = card["doom"]
    if card.get("victory") is not None:
        stats["victory"] = card["victory"]
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
        "back_text": card.get("back_text", ""),
        "back_text_cn": card.get("back_text_cn", ""),
        "stats": stats,
        "meta": {
            "subname": card.get("subname", ""),
            "subname_cn": card.get("subname_cn", ""),
            "position": card.get("position", 0),
            "quantity": card.get("quantity", 1),
        },
    }


def card_to_player_format(card: dict) -> dict:
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
            "Hand": "hand", "Hand x2": "hand_x2", "Accessory": "accessory",
            "Ally": "ally", "Arcane": "arcane", "Arcane x2": "arcane_x2",
            "Body": "body",
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
        "pack": PACK_ID,
    }

    uses = parse_uses(card.get("text"))
    if uses:
        result["uses"] = uses

    if card.get("subtype_code") == "weakness":
        result["subtype"] = "weakness"
    if card.get("subtype_code") == "basicweakness":
        result["subtype"] = "basic_weakness"
    if card.get("fast"):
        result["fast"] = True

    return result


def card_to_investigator_format(card: dict) -> dict:
    """注意：deck_requirements / signature_cards / weakness 需人工复核（卡尔克萨
    调查员全部是非标准构筑规则）。elder_sign 从文本提取。"""
    card_id = code_to_id(card.get("name", card["code"]))

    skills = {}
    for skill in ("willpower", "intellect", "combat", "agility"):
        skills[skill] = card.get(f"skill_{skill}", 0) or 0

    faction = card.get("faction_code", "neutral")

    # 从文本拆出远古印记效果（[elder_sign] 开头的句子）
    elder_sign = ""
    elder_sign_cn = ""
    text = card.get("text", "") or ""
    text_cn = card.get("text_cn", "") or ""
    m = re.search(r"\[elder_sign\][^\[]*", text)
    if m:
        elder_sign = m.group(0).strip()
    m = re.search(r"\[elder_sign\][^\[]*", text_cn)
    if m:
        elder_sign_cn = m.group(0).strip()

    deck_req = {
        "size": 30,
        "cards": {
            faction: {"min_level": 0, "max_level": 5},
            "neutral": {"min_level": 0, "max_level": 5},
        },
        "_todo": "人工复核：卡尔克萨调查员为非标准构筑（Minh/Sefina/Yorick 副职0-2、Lola 角色机制、Akachi/Mark 专属规则）",
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
        "ability": text,
        "ability_cn": text_cn,
        "elder_sign": elder_sign,
        "elder_sign_cn": elder_sign_cn,
        "deck_requirements": deck_req,
        "signature_cards": [],
        "weakness": "",
        "flavor_text": card.get("flavor", ""),
        "pack": PACK_ID,
    }


def main():
    print("Fetching The Path to Carcosa cards from ArkhamDB...")

    print("\n[1/4] Fetching EN encounter cards (ptcc)...")
    en_encounter = fetch_json(EN_API.format(pack=ENCOUNTER_PACK))
    print(f"  Got {len(en_encounter)} EN cards")

    print("[2/4] Fetching ZH encounter cards (ptcc)...")
    time.sleep(1)
    zh_encounter = fetch_json(ZH_API.format(pack=ENCOUNTER_PACK))
    print(f"  Got {len(zh_encounter)} ZH cards")

    encounter_merged = merge_en_zh(en_encounter, zh_encounter)

    print("[3/4] Fetching EN player cards (ptcp)...")
    time.sleep(1)
    en_player = fetch_json(EN_API.format(pack=PLAYER_PACK))
    print(f"  Got {len(en_player)} EN cards")

    print("[4/4] Fetching ZH player cards (ptcp)...")
    time.sleep(1)
    zh_player = fetch_json(ZH_API.format(pack=PLAYER_PACK))
    print(f"  Got {len(zh_player)} ZH cards")

    player_merged = merge_en_zh(en_player, zh_player)

    # Encounter cards — deduplicate IDs with _a/_b/_c suffixes
    raw_entries = [card_to_encounter_format(card) for card in encounter_merged]
    id_counts = Counter(e["id"] for e in raw_entries)
    seen: dict[str, int] = {}
    encounter_cards = []
    for entry in raw_entries:
        base_id = entry["id"]
        if id_counts[base_id] > 1:
            idx = seen.get(base_id, 0)
            entry["id"] = f"{base_id}_{chr(ord('a') + idx)}"
            seen[base_id] = idx + 1
        encounter_cards.append(entry)

    encounter_db = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source": "https://arkhamdb.com/api/public/cards/ptcc + zh.arkhamdb.com",
        "code_range": [3001, 3342],
        "cards": encounter_cards,
    }

    out_enc = PROJECT_ROOT / "data" / "encounter_cards" / f"{PACK_ID}.json"
    out_enc.write_text(json.dumps(encounter_db, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n✅ Wrote {len(encounter_cards)} encounter cards to {out_enc}")

    # Player cards & investigators
    investigators = []
    player_cards = []
    for card in player_merged:
        if card.get("type_code") == "investigator":
            investigators.append(card_to_investigator_format(card))
        else:
            player_cards.append(card_to_player_format(card))

    inv_dir = PROJECT_ROOT / "data" / "investigators"
    for inv in investigators:
        inv_path = inv_dir / f"{inv['id']}.json"
        inv_path.write_text(json.dumps(inv, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"  ✅ Wrote investigator: {inv_path.name}（deck 规则待人工复核）")

    for pc in player_cards:
        pc_class = pc.get("class", "neutral")
        pc_dir = PROJECT_ROOT / "data" / "player_cards" / pc_class
        pc_dir.mkdir(parents=True, exist_ok=True)
        pc_path = pc_dir / f"{pc['id']}.json"
        pc_path.write_text(json.dumps(pc, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"  ✅ Wrote {len(player_cards)} player cards")
    print(f"  ✅ Wrote {len(investigators)} investigators")

    types = {}
    for c in encounter_cards:
        types[c["type"]] = types.get(c["type"], 0) + 1
    print(f"\n📊 Encounter card breakdown:")
    for t, count in sorted(types.items()):
        print(f"  {t}: {count}")

    enc_codes = sorted({c["encounter_code"] for c in encounter_cards if c["encounter_code"]})
    print(f"\n📋 Encounter codes ({len(enc_codes)}):")
    for code in enc_codes:
        n = len([c for c in encounter_cards if c["encounter_code"] == code])
        print(f"  {code}: {n} cards")


if __name__ == "__main__":
    main()
