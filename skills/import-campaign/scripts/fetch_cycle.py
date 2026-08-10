#!/usr/bin/env python3
"""Fetch a full AHLCG cycle's player cards + investigators from ArkhamDB (EN+ZH merge).

Usage:
    python3 skills/import-campaign/scripts/fetch_cycle.py tfap the_forgotten_age
    python3 skills/import-campaign/scripts/fetch_cycle.py tcup the_circle_undone
    python3 skills/import-campaign/scripts/fetch_cycle.py tdep the_dream_eaters
    python3 skills/import-campaign/scripts/fetch_cycle.py ticp innsmouth_conspiracy
    python3 skills/import-campaign/scripts/fetch_cycle.py eoep edge_of_the_earth

Outputs:
    data/player_cards/{class}/{id}.json   — player cards (skips ids that already exist)
    data/investigators/{id}.json          — investigators (deck 规则用 deck_options 结构化生成)
"""

import json
import re
import sys
import time
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent

EN_API = "https://arkhamdb.com/api/public/cards/{pack}"
ZH_API = "https://zh.arkhamdb.com/api/public/cards/{pack}"

USES_KEY = {
    "charge": "charges", "supply": "supplies", "secret": "secrets",
    "ammo": "ammo", "offering": "offerings", "key": "keys", "doom": "doom",
    "evidence": "evidence", "bounty": "bounties",
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


def merge_en_zh(en_cards, zh_cards):
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


def parse_traits_dotted(traits_str):
    if not traits_str:
        return []
    return [p.strip().lower() for p in traits_str.split(".") if p.strip()]


def parse_uses(text):
    if not text:
        return None
    m = re.search(r"Uses \((\d+) (\w+)\)", text)
    if not m:
        return None
    n, kind = int(m.group(1)), m.group(2).lower()
    kind = USES_KEY.get(kind) or USES_KEY.get(kind.rstrip("s")) or kind
    return {kind: n}


def card_to_player_format(card, pack_id):
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
            "Body": "body", "Tarot": "tarot",
        }
        slots = [slot_map.get(slot_str, slot_str.lower())]

    faction = card.get("faction_code", "neutral")
    result = {
        "id": card_id,
        "arkhamdb_code": card["code"],
        "name": card.get("name", ""),
        "name_cn": card.get("name_cn", ""),
        "class": faction,
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
        "pack": pack_id,
    }

    # 多阵营卡（EOE 起）：faction2_code/faction3_code
    classes = [faction]
    for k in ("faction2_code", "faction3_code"):
        f2 = card.get(k)
        if f2 and f2 not in classes:
            classes.append(f2)
    if len(classes) > 1:
        result["classes"] = classes

    if card.get("subname"):
        result["subname"] = card.get("subname")
        result["subname_cn"] = card.get("subname_cn", "")
    if card.get("fast"):
        result["fast"] = True
    uses = parse_uses(card.get("text"))
    if uses:
        result["uses"] = uses
    if card.get("subtype_code") == "weakness":
        result["subtype"] = "weakness"
    if card.get("subtype_code") == "basicweakness":
        result["subtype"] = "basic_weakness"
    if card.get("myriad"):
        result["myriad"] = True
    if card.get("exceptional"):
        result["exceptional"] = True
    return result


def card_to_investigator_format(card, pack_id):
    card_id = code_to_id(card.get("name", card["code"]))
    skills = {s: card.get(f"skill_{s}", 0) or 0
              for s in ("willpower", "intellect", "combat", "agility")}
    faction = card.get("faction_code", "neutral")

    text = card.get("text", "") or ""
    text_cn = card.get("text_cn", "") or ""
    elder_sign = ""
    elder_sign_cn = ""
    m = re.search(r"\[elder_sign\][^\[]*", text)
    if m:
        elder_sign = m.group(0).strip()
    m = re.search(r"\[elder_sign\][^\[]*", text_cn)
    if m:
        elder_sign_cn = m.group(0).strip()

    # deck_options → 项目格式
    cards_req = {}
    trait_opts = []
    for opt in card.get("deck_options") or []:
        factions = opt.get("faction") or []
        lv = opt.get("level") or {}
        lo, hi = lv.get("min", 0), lv.get("max", 5)
        traits = opt.get("trait") or []
        if traits:
            trait_opts.append(f"trait:{','.join(traits)} lv{lo}-{hi}")
        if factions:
            if set(factions) >= {"guardian", "seeker", "rogue", "mystic", "survivor", "neutral"}:
                cards_req["any"] = {"min_level": lo, "max_level": hi}
            else:
                for f in factions:
                    cards_req[f] = {"min_level": lo, "max_level": hi}
    deck_req = {"size": (card.get("deck_requirements") or {}).get("size", 30), "cards": cards_req}
    if trait_opts:
        deck_req["_trait_options"] = trait_opts

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
        "signature_cards": [],   # 由主流程按 deck_requirements.card 回填
        "weakness": "",
        "flavor_text": card.get("flavor", ""),
        "back_text": card.get("back_text", ""),
        "back_text_cn": card.get("back_text_cn", ""),
        "pack": pack_id,
    }


def main():
    pack = sys.argv[1]
    pack_id = sys.argv[2]
    print(f"Fetching {pack} → {pack_id} ...")

    en = fetch_json(EN_API.format(pack=pack))
    print(f"  EN: {len(en)} cards")
    time.sleep(1)
    zh = fetch_json(ZH_API.format(pack=pack))
    print(f"  ZH: {len(zh)} cards")
    merged = merge_en_zh(en, zh)

    # 现有数据 id 集合（防撞名/重印）
    existing = {}
    for p in (PROJECT_ROOT / "data" / "player_cards").rglob("*.json"):
        if p.name == "schema.json":
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        existing[d["id"]] = str(p)

    investigators = []
    player_cards = []
    skipped_dupes = []
    for card in merged:
        if card.get("type_code") == "investigator":
            investigators.append(card_to_investigator_format(card, pack_id))
        else:
            pc = card_to_player_format(card, pack_id)
            if pc["id"] in existing:
                skipped_dupes.append((pc["id"], card.get("code")))
                continue
            player_cards.append(pc)

    inv_dir = PROJECT_ROOT / "data" / "investigators"
    for inv in investigators:
        inv_path = inv_dir / f"{inv['id']}.json"
        inv_path.write_text(json.dumps(inv, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"  ✅ investigator: {inv['id']} ({inv['name_cn']})")

    for pc in player_cards:
        pc_dir = PROJECT_ROOT / "data" / "player_cards" / pc.get("class", "neutral")
        pc_dir.mkdir(parents=True, exist_ok=True)
        (pc_dir / f"{pc['id']}.json").write_text(
            json.dumps(pc, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"  ✅ {len(player_cards)} player cards written; {len(investigators)} investigators")
    if skipped_dupes:
        print(f"  ⏭️ 跳过已有同 id 卡（沿用旧数据）: {[d[0] for d in skipped_dupes]}")
    # 多阵营卡提示
    multi = [c["id"] for c in player_cards if c.get("classes")]
    if multi:
        print(f"  🎨 多阵营卡: {multi}")


if __name__ == "__main__":
    main()
