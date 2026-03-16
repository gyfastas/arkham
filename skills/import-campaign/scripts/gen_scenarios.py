#!/usr/bin/env python3
"""Generate scenario definition JSONs for The Dunwich Legacy campaign.

Uses encounter_cards/dunwich_legacy.json to extract location/act/agenda data,
then writes scenario files with connections and encounter set references.

Usage:
    python3 skills/import-campaign/scripts/gen_scenarios.py
"""

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
ENCOUNTER_DB = PROJECT_ROOT / "data" / "encounter_cards" / "dunwich_legacy.json"
SCENARIO_DIR = PROJECT_ROOT / "data" / "scenarios"
CAMPAIGN_DIR = PROJECT_ROOT / "data" / "campaigns"


def load_db() -> dict[str, dict]:
    data = json.load(open(ENCOUNTER_DB, encoding="utf-8"))
    return {c["id"]: c for c in data["cards"]}


# ============================================================
# Scenario definitions — manually curated from ArkhamDB scenario guides
# Each has: encounter_sets, start_location, connections, story_assets
# ============================================================

SCENARIOS = [
    {
        "id": "extracurricular_activity",
        "name": "Extracurricular Activity",
        "name_cn": "课外活动",
        "sequence": 1,
        "encounter_sets": [
            "extracurricular_activity",
            "sorcery",
            "bishops_thralls",
            "whippoorwills",
            "ancient_evils",  # from core
            "locked_doors",   # from core
        ],
        "scenario_set": "extracurricular_activity",
        "start_location": "miskatonic_quad",
        "connections": {
            "miskatonic_quad": ["humanities_building", "orne_library", "student_union", "administration_building", "science_building"],
            "humanities_building": ["miskatonic_quad", "student_union"],
            "orne_library": ["miskatonic_quad", "student_union"],
            "student_union": ["miskatonic_quad", "humanities_building", "orne_library", "dormitories", "administration_building"],
            "dormitories": ["student_union"],
            "administration_building": ["miskatonic_quad", "student_union", "faculty_offices_a"],
            "faculty_offices_a": ["administration_building"],
            "science_building": ["miskatonic_quad", "alchemy_labs"],
            "alchemy_labs": ["science_building"],
        },
        "locations": [
            "miskatonic_quad", "humanities_building", "orne_library", "student_union",
            "dormitories", "administration_building", "faculty_offices_a",
            "science_building", "alchemy_labs",
        ],
        "story_assets": ["dr_henry_armitage", "professor_warren_rice", "jazz_mulligan", "alchemical_concoction"],
    },
    {
        "id": "the_house_always_wins",
        "name": "The House Always Wins",
        "name_cn": "百赌百胜",
        "sequence": 2,
        "encounter_sets": [
            "the_house_always_wins",
            "bad_luck",
            "naomis_crew",
            "rats",            # from core
            "striking_fear",   # from core
        ],
        "scenario_set": "the_house_always_wins",
        "start_location": "la_bella_luna",
        "connections": {
            "la_bella_luna": ["clover_club_lounge"],
            "clover_club_lounge": ["la_bella_luna", "clover_club_bar", "clover_club_cardroom"],
            "clover_club_bar": ["clover_club_lounge"],
            "clover_club_cardroom": ["clover_club_lounge"],
            "darkened_hall": ["clover_club_lounge", "art_gallery", "vip_area", "back_alley"],
            "art_gallery": ["darkened_hall"],
            "vip_area": ["darkened_hall"],
            "back_alley": ["darkened_hall"],
        },
        "locations": [
            "la_bella_luna", "clover_club_lounge", "clover_club_bar",
            "clover_club_cardroom", "darkened_hall", "art_gallery", "vip_area", "back_alley",
        ],
        "story_assets": ["dr_francis_morgan", "peter_clover"],
    },
    {
        "id": "the_miskatonic_museum",
        "name": "The Miskatonic Museum",
        "name_cn": "米斯卡塔尼克博物馆",
        "sequence": 3,
        "encounter_sets": [
            "the_miskatonic_museum",
            "bad_luck",
            "sorcery",
            "the_beyond",
            "chilling_cold",   # from core
        ],
        "scenario_set": "the_miskatonic_museum",
        "start_location": "museum_entrance",
        "connections": {
            "museum_entrance": ["museum_halls"],
            "museum_halls": ["museum_entrance", "security_office_a", "administration_office_a", "exhibit_hall_a"],
            "security_office_a": ["museum_halls"],
            "administration_office_a": ["museum_halls"],
            "exhibit_hall_a": ["museum_halls", "exhibit_hall_b", "exhibit_hall_c"],
            "exhibit_hall_b": ["exhibit_hall_a", "exhibit_hall_d"],
            "exhibit_hall_c": ["exhibit_hall_a", "exhibit_hall_e"],
            "exhibit_hall_d": ["exhibit_hall_b", "exhibit_hall_f"],
            "exhibit_hall_e": ["exhibit_hall_c", "exhibit_hall_f"],
            "exhibit_hall_f": ["exhibit_hall_d", "exhibit_hall_e"],
        },
        "locations": [
            "museum_entrance", "museum_halls", "security_office_a",
            "administration_office_a", "exhibit_hall_a", "exhibit_hall_b",
            "exhibit_hall_c", "exhibit_hall_d", "exhibit_hall_e", "exhibit_hall_f",
        ],
        "story_assets": ["harold_walsted", "adam_lynch", "the_necronomicon"],
    },
    {
        "id": "essex_county_express",
        "name": "Essex County Express",
        "name_cn": "埃塞克斯县快车",
        "sequence": 4,
        "encounter_sets": [
            "essex_county_express",
            "dunwich",
            "the_beyond",
            "striking_fear",   # from core
        ],
        "scenario_set": "essex_county_express",
        "start_location": "engine_car_a",
        "connections": {
            "engine_car_a": ["parlor_car"],
            "parlor_car": ["engine_car_a", "dining_car"],
            "dining_car": ["parlor_car", "sleeping_car"],
            "sleeping_car": ["dining_car", "passenger_car_a"],
            "passenger_car_a": ["sleeping_car", "passenger_car_b"],
            "passenger_car_b": ["passenger_car_a", "passenger_car_c"],
            "passenger_car_c": ["passenger_car_b", "passenger_car_d"],
            "passenger_car_d": ["passenger_car_c", "passenger_car_e"],
            "passenger_car_e": ["passenger_car_d"],
        },
        "locations": [
            "engine_car_a", "parlor_car", "dining_car", "sleeping_car",
            "passenger_car_a", "passenger_car_b", "passenger_car_c",
            "passenger_car_d", "passenger_car_e",
        ],
        "story_assets": ["helpless_passenger"],
    },
    {
        "id": "blood_on_the_altar",
        "name": "Blood on the Altar",
        "name_cn": "祭坛之血",
        "sequence": 5,
        "encounter_sets": [
            "blood_on_the_altar",
            "dunwich",
            "whippoorwills",
            "beast_thralls",
            "nightgaunts",     # from core
        ],
        "scenario_set": "blood_on_the_altar",
        "start_location": "village_commons",
        "connections": {
            "village_commons": ["bishops_brook_a", "burned_ruins_a", "osborns_general_store_a", "congregational_church_a"],
            "bishops_brook_a": ["village_commons", "burned_ruins_a"],
            "burned_ruins_a": ["village_commons", "bishops_brook_a", "osborns_general_store_a"],
            "osborns_general_store_a": ["village_commons", "burned_ruins_a", "congregational_church_a"],
            "congregational_church_a": ["village_commons", "osborns_general_store_a", "house_in_the_reeds_a"],
            "house_in_the_reeds_a": ["congregational_church_a", "schoolhouse_a"],
            "schoolhouse_a": ["house_in_the_reeds_a"],
            "the_hidden_chamber": ["village_commons"],
        },
        "locations": [
            "village_commons", "bishops_brook_a", "burned_ruins_a",
            "osborns_general_store_a", "congregational_church_a",
            "house_in_the_reeds_a", "schoolhouse_a", "the_hidden_chamber",
        ],
        "story_assets": ["key_to_the_chamber", "zebulon_whateley", "earl_sawyer", "powder_of_ibn_ghazi"],
    },
    {
        "id": "undimensioned_and_unseen",
        "name": "Undimensioned and Unseen",
        "name_cn": "无形无踪",
        "sequence": 6,
        "encounter_sets": [
            "undimensioned_and_unseen",
            "whippoorwills",
            "beast_thralls",
            "dunwich",
            "striking_fear",   # from core
        ],
        "scenario_set": "undimensioned_and_unseen",
        "start_location": "dunwich_village_a",
        "connections": {
            "dunwich_village_a": ["cold_spring_glen_a", "ten_acre_meadow_a", "whateley_ruins_a"],
            "cold_spring_glen_a": ["dunwich_village_a", "ten_acre_meadow_a", "blasted_heath_a"],
            "ten_acre_meadow_a": ["dunwich_village_a", "cold_spring_glen_a", "whateley_ruins_a", "devils_hop_yard_a"],
            "blasted_heath_a": ["cold_spring_glen_a", "whateley_ruins_a", "devils_hop_yard_a"],
            "whateley_ruins_a": ["dunwich_village_a", "ten_acre_meadow_a", "blasted_heath_a"],
            "devils_hop_yard_a": ["ten_acre_meadow_a", "blasted_heath_a"],
        },
        "locations": [
            "dunwich_village_a", "cold_spring_glen_a", "ten_acre_meadow_a",
            "blasted_heath_a", "whateley_ruins_a", "devils_hop_yard_a",
        ],
        "story_assets": ["esoteric_formula"],
    },
    {
        "id": "where_doom_awaits",
        "name": "Where Doom Awaits",
        "name_cn": "末日将至",
        "sequence": 7,
        "encounter_sets": [
            "where_doom_awaits",
            "bishops_thralls",
            "beast_thralls",
            "sorcery",
            "ancient_evils",   # from core
        ],
        "scenario_set": "where_doom_awaits",
        "start_location": "base_of_the_hill",
        "connections": {
            "base_of_the_hill": ["ascending_path"],
            "ascending_path": ["base_of_the_hill", "sentinel_peak", "slaughtered_woods", "eerie_glade"],
            "sentinel_peak": ["ascending_path"],
            "slaughtered_woods": ["ascending_path", "destroyed_path"],
            "eerie_glade": ["ascending_path", "frozen_spring"],
            "destroyed_path": ["slaughtered_woods", "dimensional_gap"],
            "frozen_spring": ["eerie_glade", "dimensional_gap"],
            "dimensional_gap": ["destroyed_path", "frozen_spring"],
        },
        "locations": [
            "base_of_the_hill", "ascending_path", "sentinel_peak",
            "slaughtered_woods", "eerie_glade", "destroyed_path",
            "frozen_spring", "dimensional_gap",
        ],
        "story_assets": [],
    },
    {
        "id": "lost_in_time_and_space",
        "name": "Lost in Time and Space",
        "name_cn": "迷失于时空",
        "sequence": 8,
        "encounter_sets": [
            "lost_in_time_and_space",
            "the_beyond",
            "hideous_abominations",
            "sorcery",
            "ancient_evils",   # from core
        ],
        "scenario_set": "lost_in_time_and_space",
        "start_location": "another_dimension",
        "connections": {
            "another_dimension": ["the_edge_of_the_universe", "tear_through_time"],
            "the_edge_of_the_universe": ["another_dimension", "tear_through_space"],
            "tear_through_time": ["another_dimension", "prismatic_cascade"],
            "tear_through_space": ["the_edge_of_the_universe", "endless_bridge"],
            "prismatic_cascade": ["tear_through_time", "steps_of_yhagharl"],
            "endless_bridge": ["tear_through_space", "steps_of_yhagharl"],
            "steps_of_yhagharl": ["prismatic_cascade", "endless_bridge", "dimensional_doorway"],
            "dimensional_doorway": ["steps_of_yhagharl"],
        },
        "locations": [
            "another_dimension", "the_edge_of_the_universe", "tear_through_time",
            "tear_through_space", "prismatic_cascade", "endless_bridge",
            "steps_of_yhagharl", "dimensional_doorway",
        ],
        "story_assets": [],
    },
]


def main():
    db = load_db()

    for sc in SCENARIOS:
        # Resolve act/agenda decks from encounter DB
        encounter_code = sc["scenario_set"]
        acts = sorted(
            [c for c in db.values() if c["encounter_code"] == encounter_code and c["type"] == "act"],
            key=lambda c: c["meta"]["position"],
        )
        agendas = sorted(
            [c for c in db.values() if c["encounter_code"] == encounter_code and c["type"] == "agenda"],
            key=lambda c: c["meta"]["position"],
        )

        scenario_def = {
            "id": sc["id"],
            "name": sc["name"],
            "name_cn": sc["name_cn"],
            "type": "official",
            "campaign": "dunwich_legacy",
            "sequence": sc["sequence"],
            "encounter_sets": sc["encounter_sets"],
            "scenario_set": sc["scenario_set"],
            "start_location": sc["start_location"],
            "connections": sc["connections"],
            "act_deck": [a["id"] for a in acts],
            "agenda_deck": [a["id"] for a in agendas],
            "locations": sc["locations"],
            "story_assets": sc["story_assets"],
        }

        out_path = SCENARIO_DIR / f"{sc['id']}.json"
        out_path.write_text(json.dumps(scenario_def, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"✅ {sc['id']}: {len(sc['locations'])} locs, {len(acts)} acts, {len(agendas)} agendas")

    # Campaign definition
    campaign = {
        "id": "dunwich_legacy",
        "name": "The Dunwich Legacy",
        "name_cn": "敦威治遗产",
        "type": "official",
        "scenarios": [sc["id"] for sc in SCENARIOS],
        "investigators": [
            "zoey_samaras", "rex_murphy", "jenny_barnes",
            "jim_culver", "ashcan_pete",
        ],
    }
    CAMPAIGN_DIR.mkdir(parents=True, exist_ok=True)
    out_path = CAMPAIGN_DIR / "dunwich_legacy.json"
    out_path.write_text(json.dumps(campaign, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n✅ Campaign: {out_path}")


if __name__ == "__main__":
    main()
