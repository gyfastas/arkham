"""Official core set scenarios: data loader + runnable rules.

This module provides:
- Load 3 official core scenarios from `data/scenarios/*.json`
- Load their scenario/encounter cards from `data/encounter_cards/core_set.json`
- A small runtime that:
  - Builds encounter deck
  - Resolves ALL treachery cards used by the 3 core scenarios
  - Implements minimal act/agenda advancement + branching endings

Design note
-----------
The core engine is a general rules engine (phases/actions/skill tests).
Scenario-specific rules live here, so we can iterate quickly without
polluting `backend/engine/*`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SCENARIO_DIR = PROJECT_ROOT / "data" / "scenarios"
ENCOUNTER_DB_PATH = PROJECT_ROOT / "data" / "encounter_cards" / "core_set.json"
DUNWICH_DB_PATH = PROJECT_ROOT / "data" / "encounter_cards" / "dunwich_legacy.json"
CARCOSA_DB_PATH = PROJECT_ROOT / "data" / "encounter_cards" / "path_to_carcosa.json"
TFA_DB_PATH = PROJECT_ROOT / "data" / "encounter_cards" / "the_forgotten_age.json"
TCU_DB_PATH = PROJECT_ROOT / "data" / "encounter_cards" / "the_circle_undone.json"
TDE_DB_PATH = PROJECT_ROOT / "data" / "encounter_cards" / "the_dream_eaters.json"
TIC_DB_PATH = PROJECT_ROOT / "data" / "encounter_cards" / "innsmouth_conspiracy.json"
EOE_DB_PATH = PROJECT_ROOT / "data" / "encounter_cards" / "edge_of_the_earth.json"


def _load_encounter_db(path: Path) -> dict[str, dict[str, Any]]:
    payload = _load_json(path)
    cards: list[dict[str, Any]] = payload.get("cards", [])
    return {c["id"]: c for c in cards}


def _load_json(path: Path) -> Any:
    import json

    return json.loads(path.read_text(encoding="utf-8"))


def load_core_encounter_db() -> dict[str, dict[str, Any]]:
    """Return encounter/scenario card records keyed by `id`."""
    return _load_encounter_db(ENCOUNTER_DB_PATH)


def load_dunwich_encounter_db() -> dict[str, dict[str, Any]]:
    """Return Dunwich Legacy encounter card records keyed by `id`."""
    return _load_encounter_db(DUNWICH_DB_PATH)


def load_carcosa_encounter_db() -> dict[str, dict[str, Any]]:
    """Return Path to Carcosa encounter card records keyed by `id`."""
    return _load_encounter_db(CARCOSA_DB_PATH)


def load_encounter_db_for_campaign(campaign: str) -> dict[str, dict[str, Any]]:
    """Load the appropriate encounter DB(s) based on campaign.

    Non-core campaigns reference core encounter sets (rats, ancient_evils,
    etc.), so we merge the core database with the campaign's own.
    """
    if campaign == "core":
        return load_core_encounter_db()
    db = load_core_encounter_db()
    cycle_loaders = {
        "dunwich_legacy": (DUNWICH_DB_PATH,),
        "path_to_carcosa": (CARCOSA_DB_PATH,),
        "the_forgotten_age": (TFA_DB_PATH,),
        "the_circle_undone": (TCU_DB_PATH,),
        "the_dream_eaters": (TDE_DB_PATH,),
        "innsmouth_conspiracy": (TIC_DB_PATH,),
        "edge_of_the_earth": (EOE_DB_PATH,),
    }
    paths = cycle_loaders.get(campaign)
    if paths:
        for p in paths:
            db.update(_load_encounter_db(p))
    return db


def load_scenario_definition(scenario_id: str) -> dict[str, Any]:
    path = SCENARIO_DIR / f"{scenario_id}.json"
    return _load_json(path)


def apply_scenario_to_game(game, scenario_id: str, *, seed: int = 1, difficulty: str = "standard") -> None:
    """Populate `game.state` with scenario data (locations/act/agenda/encounter deck)."""
    from backend.models.chaos import build_bag_tokens
    from backend.models.enums import CardType
    from backend.models.scenario import ActCard, AgendaCard
    from backend.models.state import CardData

    scenario_def = load_scenario_definition(scenario_id)
    campaign = scenario_def.get("campaign", "core")
    db = load_encounter_db_for_campaign(campaign)

    # Official chaos bag for this campaign/difficulty (mutate in place so the
    # SkillTestEngine's bag reference stays valid; RNG seeding is untouched).
    game.chaos_bag.tokens = build_bag_tokens(campaign, difficulty)
    # 剧本级 token 增补（官方战役指南 setup，如 TCU 各章加 tablet/elder_thing）
    bag_add = scenario_def.get("bag_add") or {}
    if isinstance(bag_add, list):
        # 条件型（含 condition 的条目）暂不支持战役日志追踪——仅取无条件默认项
        bag_add = {t: len(e.get("tokens", [])) for e in bag_add
                   if isinstance(e, dict) and e.get("default")}
    if bag_add:
        from backend.models.enums import ChaosTokenType
        for value, count in bag_add.items():
            game.chaos_bag.tokens.extend([ChaosTokenType(value)] * int(count))

    s = game.state.scenario
    s.scenario_id = scenario_id
    s.vars.setdefault("scenario_id", scenario_id)
    s.vars.setdefault("scenario_name", scenario_def.get("name"))
    s.vars.setdefault("resolution_id", None)
    s.vars.setdefault("campaign", campaign)
    s.vars.setdefault("difficulty", difficulty)
    # Scenario-specific counters
    if scenario_id == "the_midnight_masks":
        s.vars.setdefault("cultists_defeated", 0)
    if scenario_id == "the_devourer_below":
        s.vars.setdefault("lita_saved", False)

    # Scenario reference card (chaos token rules)
    scenario_set = scenario_def.get("scenario_set")
    for card in db.values():
        if card.get("encounter_code") == scenario_set and card.get("type") == "scenario":
            s.scenario_card_id = card["id"]
            break

    # --- Locations (map) ---
    connections: dict[str, list[str]] = scenario_def.get("connections", {})
    # 官方布置：initial_locations 之外的地点游戏开始时不进场（doorway/后续效果带入）
    initial_locations = scenario_def.get("initial_locations")
    for loc_id in scenario_def.get("locations", []):
        if initial_locations is not None and loc_id not in initial_locations:
            continue
        rec = db.get(loc_id)
        if not rec or rec.get("type") != "location":
            raise ValueError(f"missing location in encounter db: {loc_id}")
        shroud = (rec.get("stats") or {}).get("shroud")
        clues = (rec.get("stats") or {}).get("clues")
        cd = CardData(
            id=loc_id,
            name=rec.get("name") or loc_id,
            name_cn=rec.get("name_cn") or "",
            type=CardType.LOCATION,
            shroud=int(shroud) if shroud is not None else 0,
            clue_value=int(clues) if clues is not None else 0,
            connections=connections.get(loc_id, []),
            text=rec.get("text") or "",
            traits=(rec.get("traits") or []),
            # 官方地点线索值为 ⊘（每调查员）；setup 时按人数缩放
            per_investigator=bool(clues),
        )
        game.register_card_data(cd)
        game.add_location(loc_id, cd, clues=cd.clue_value or 0)

    # --- Act / Agenda decks ---
    s.act_deck = list(scenario_def.get("act_deck", []))
    s.agenda_deck = list(scenario_def.get("agenda_deck", []))

    # Minimal clue thresholds (from scenario guide; used only for deterministic tests)
    clue_thresholds: dict[str, int] = {
        # The Gathering
        "trapped": 2,
        "the_barrier": 6,
        "what_have_you_done": 0,
        # The Midnight Masks
        "uncovering_the_conspiracy": 0,
        # The Devourer Below
        "the_devourer_below": 2,
        "searching_for_the_ritual": 4,
        "into_the_dark": 0,
        # Extracurricular Activity
        "after_hours": 3,
        "rices_whereabouts": 0,
        "campus_safety": 0,
        # The House Always Wins
        "beginners_luck": 4,
        "skin_game": 2,
        "all_in": 0,
        "fold": 0,
        # The Miskatonic Museum
        "finding_a_way_inside": 0,
        "night_at_the_museum": 0,
        "breaking_and_entering": 0,
        "searching_for_the_tome": 0,
        # Essex County Express
        "run": 0,
        "get_the_engine_running": 0,
        # Blood on the Altar
        "searching_for_answers": 0,
        "the_chamber_of_the_beast": 0,
        # Undimensioned and Unseen
        "saracenic_script": 0,
        "they_must_be_destroyed": 0,
        # Where Doom Awaits
        "the_path_to_the_hill": 3,
        "ascending_the_hill_v_i": 0,
        "ascending_the_hill_v_ii": 0,
        "ascending_the_hill_v_iii": 0,
        "the_gate_opens": 0,
        # Lost in Time and Space
        "out_of_this_world": 0,
        "into_the_beyond": 0,
        "close_the_rift": 0,
        "finding_a_new_way": 0,
    }

    s.act_cards = {}
    for act_id in s.act_deck:
        rec = db.get(act_id)
        if not rec or rec.get("type") != "act":
            raise ValueError(f"missing act in encounter db: {act_id}")
        # 线索阈值：优先用遭遇库官方数值（stats.clues；clues_fixed=False 即
        # 官方 ⊘ 每调查员标记，运行时×人数）；库中缺失时退回剧本指南硬编码
        stats = rec.get("stats") or {}
        per_inv = False
        if stats.get("clues") is not None:
            threshold = int(stats["clues"])
            per_inv = not bool(stats.get("clues_fixed", False))
        else:
            threshold = clue_thresholds.get(act_id)
        s.act_cards[act_id] = ActCard(
            id=act_id,
            name=rec.get("name") or act_id,
            name_cn=rec.get("name_cn") or "",
            sequence=int((rec.get("meta") or {}).get("position") or 1),
            clue_threshold=threshold,
            clue_threshold_per_investigator=per_inv,
            text=rec.get("text") or "",
            text_cn=rec.get("text_cn") or "",
            back_text=rec.get("back_text") or "",
            back_text_cn=rec.get("back_text_cn") or "",
        )

    s.agenda_cards = {}
    for agenda_id in s.agenda_deck:
        rec = db.get(agenda_id)
        if not rec or rec.get("type") != "agenda":
            raise ValueError(f"missing agenda in encounter db: {agenda_id}")
        doom = (rec.get("stats") or {}).get("doom")
        s.agenda_cards[agenda_id] = AgendaCard(
            id=agenda_id,
            name=rec.get("name") or agenda_id,
            name_cn=rec.get("name_cn") or "",
            doom_threshold=int(doom) if doom is not None else s.doom_threshold,
            sequence=int((rec.get("meta") or {}).get("position") or 1),
            text=rec.get("text") or "",
            text_cn=rec.get("text_cn") or "",
            back_text=rec.get("back_text") or "",
            back_text_cn=rec.get("back_text_cn") or "",
        )

    # --- Encounter deck ---
    encounter_sets: list[str] = scenario_def.get("encounter_sets", [])
    deck: list[str] = []

    # Scenario set-aside cards (official rules); keep them out of encounter deck
    # but still register their card data (effects bring them into play later).
    set_aside: set[str] = set(scenario_def.get("set_aside", []))
    if scenario_id == "the_gathering":
        set_aside.update({"ghoul_priest", "lita_chantler"})
    for rec in db.values():
        if rec.get("encounter_code") not in encounter_sets:
            continue
        t = rec.get("type")
        if t in ("enemy", "treachery", "location"):
            # Location cards never belong in the encounter deck (previously
            # only scenario_def.locations were excluded, leaking _b variants)
            if t == "location":
                continue
            # 官方：遭遇牌堆含 meta.quantity 份（库中缺失时按 1）
            qty = int((rec.get("meta") or {}).get("quantity") or 1)
            if rec.get("id") not in set_aside:
                deck.extend([rec["id"]] * qty)

            # Register enemy data for spawning / defeat tracking
            if t == "enemy":
                stats = rec.get("stats") or {}
                cd = CardData(
                    id=rec["id"],
                    name=rec.get("name") or rec["id"],
                    name_cn=rec.get("name_cn") or "",
                    type=CardType.ENEMY,
                    enemy_fight=stats.get("fight"),
                    enemy_health=stats.get("health"),
                    enemy_evade=stats.get("evade"),
                    enemy_damage=stats.get("damage"),
                    enemy_horror=stats.get("horror"),
                    traits=(rec.get("traits") or []),
                    keywords=_derive_enemy_keywords(rec),
                    text=rec.get("text") or "",
                    text_cn=rec.get("text_cn") or "",
                    victory=int(rec.get("victory") or 0),
                )
                game.register_card_data(cd)

            # Register treachery data (needed by location attachments /
            # client display for cards like Locked Door, Obscuring Fog)
            elif t == "treachery":
                cd = CardData(
                    id=rec["id"],
                    name=rec.get("name") or rec["id"],
                    name_cn=rec.get("name_cn") or "",
                    type=CardType.TREACHERY,
                    traits=(rec.get("traits") or []),
                    text=rec.get("text") or "",
                    text_cn=rec.get("text_cn") or "",
                )
                game.register_card_data(cd)

    import random

    rnd = random.Random(seed)
    rnd.shuffle(deck)
    s.encounter_deck = deck
    s.encounter_discard = []


def _margin_fail(result) -> int:
    """Return fail-by margin (>=0)."""
    if result is None:
        return 0
    diff = getattr(result, "difficulty", 0) or 0
    mod = getattr(result, "modified_skill", 0) or 0
    return max(0, diff - mod)


def _draw_cards(game, investigator_id: str, n: int) -> int:
    inv = game.state.get_investigator(investigator_id)
    if inv is None:
        return 0
    drew = 0
    for _ in range(n):
        if inv.deck:
            inv.hand.append(inv.deck.pop(0))
            drew += 1
        elif inv.discard:
            # simple reshuffle
            import random

            inv.deck = list(inv.discard)
            inv.discard.clear()
            random.shuffle(inv.deck)
            inv.hand.append(inv.deck.pop(0))
            drew += 1
        else:
            break
    return drew


def _find_location_by_name(game, name: str) -> str | None:
    """Match by English or Chinese location name."""
    if not name:
        return None
    key = name.strip().lower()
    for loc_id, loc in game.state.locations.items():
        if (loc.card_data.name or "").strip().lower() == key:
            return loc_id
        if (loc.card_data.name_cn or "").strip().lower() == key:
            return loc_id
    return None


def _parse_spawn_location_from_text(text: str) -> str | None:
    """Extract a spawn location name from English/Chinese text."""
    if not text:
        return None
    # English: "Spawn - Attic." ; Chinese (zh arkhamdb): "生成 - 閣樓。"
    for marker in ("Spawn", "生成"):
        if marker in text:
            # take substring after marker
            tail = text.split(marker, 1)[1]
            # find '-' separator
            if "-" in tail:
                tail = tail.split("-", 1)[1]
            tail = tail.strip()
            # truncate at punctuation
            for sep in (".", "。", "\n"):
                if sep in tail:
                    tail = tail.split(sep, 1)[0]
            return tail.strip()
    return None


def _is_nightgaunt(card_id: str) -> bool:
    return card_id in {"nightgaunt"} or "nightgaunt" in (card_id or "")


# Chinese trait → English keyword (encounter DB traits are Chinese)
_TRAIT_TO_KEYWORD = {
    "精英": "elite",
    "食屍鬼": "ghoul",
    "怪物": "monster",
    "異教徒": "cultist",
    "古神": "ancient_one",
    "夜魘": "nightgaunt",
    "類人": "humanoid",
    "附身": "possessed",
    "拜亞基": "byakhee",
    "靈怪": "specter",
}

# Text keyword (Chinese/English) → engine keyword
_TEXT_KEYWORDS = [
    ("獵手", "hunter"), ("Hunter", "hunter"),
    ("警覺", "alert"), ("Alert", "alert"),
    ("巨大", "massive"), ("Massive", "massive"),
    ("冷漠", "aloof"), ("Aloof", "aloof"),
    ("報復", "retaliate"), ("Retaliate", "retaliate"),
    ("反擊", "retaliate"),
    ("隱藏", "hidden"), ("Hidden", "hidden"),
]


def _derive_enemy_keywords(rec: dict) -> list[str]:
    """Populate engine keywords from encounter DB record (traits + text).

    Without this, enemy CardData.keywords is always empty and hunter/alert/
    elite checks silently never match.
    """
    keywords: list[str] = []
    for trait in rec.get("traits") or []:
        kw = _TRAIT_TO_KEYWORD.get(trait)
        if kw and kw not in keywords:
            keywords.append(kw)
    text = (rec.get("text") or "")
    for marker, kw in _TEXT_KEYWORDS:
        if marker in text and kw not in keywords:
            keywords.append(kw)
    return keywords


def is_elite_enemy(card_data) -> bool:
    """Check elite status across Chinese traits and English keywords."""
    traits = getattr(card_data, "traits", None) or []
    keywords = getattr(card_data, "keywords", None) or []
    return "elite" in keywords or "精英" in traits


def _is_cultist_enemy_id(card_id: str) -> bool:
    # For core set, treat encounter sets 'cultists' and 'pentagram' as cultist enemies.
    # (Dark Cult has cultists; Cult of Umôrdhoth are cultists)
    return card_id in {
        "acolyte",
        "wizard_of_the_order",
        "wolf_man_drew",
        "victoria_devereux",
        "herman_collins",
        "peter_warren",
        "mask_of_um_rdhoth",
        "disciple_of_the_devourer",
        "brood_of_um_rdhoth",
    }


DUNWICH_SCENARIO_IDS = {
    "extracurricular_activity", "the_house_always_wins", "the_miskatonic_museum",
    "essex_county_express", "blood_on_the_altar", "undimensioned_and_unseen",
    "where_doom_awaits", "lost_in_time_and_space",
}

CARCOSA_SCENARIO_IDS = {
    "curtain_call", "the_last_king", "echoes_of_the_past",
    "the_unspeakable_oath", "a_phantom_of_truth", "the_pallid_mask",
    "black_stars_rise", "dim_carcosa",
}

# 循环 3-7（TFA/TCU/TDE/TIC/EOE）的符号 token 效果由各循环模块实现：
# backend/scenarios/tokens_{cyc}.py，导出 apply_token/on_fail/on_success。
_CYCLE_TOKEN_MODULES = {
    "the_forgotten_age": "tokens_tfa",
    "the_circle_undone": "tokens_tcu",
    "the_dream_eaters": "tokens_tde",
    "innsmouth_conspiracy": "tokens_tic",
    "edge_of_the_earth": "tokens_eoe",
}

_CYCLE_ENCOUNTER_MODULES = {
    "the_forgotten_age": "encounters_the_forgotten_age",
    "the_circle_undone": "encounters_the_circle_undone",
    "the_dream_eaters": "encounters_the_dream_eaters",
    "innsmouth_conspiracy": "encounters_innsmouth_conspiracy",
    "edge_of_the_earth": "encounters_edge_of_the_earth",
}


def _cycle_for_scenario(scenario_id: str) -> str | None:
    """按剧本定义 JSON 的 campaign 字段判断所属循环。"""
    try:
        return load_scenario_definition(scenario_id).get("campaign")
    except Exception:
        return None


@dataclass
class ScenarioController:
    """Scenario-specific glue: encounter resolution + branching endings.

    This controller is designed to be used by a server loop that drives
    end-of-turn / mythos flow.
    """

    game: Any
    action_log: list[str] | None = None
    skill_test_request_handler: Callable[..., Any] | None = None

    def attach(self) -> None:
        """Attach handlers to the game's event bus."""
        from backend.models.enums import GameEvent, TimingPriority

        self.game.event_bus.register(
            GameEvent.SKILL_VALUE_DETERMINED,
            self._skill_modifiers,
            priority=TimingPriority.WHEN,
        )
        self.game.event_bus.register(GameEvent.CLUE_DISCOVERED, self._on_clue_discovered)
        self.game.event_bus.register(GameEvent.ENEMY_DEFEATED, self._on_enemy_defeated)
        self.game.event_bus.register(GameEvent.AGENDA_ADVANCED, self._on_agenda_advanced)

        # Scenario-specific chaos token effects (skull/cultist/tablet/elder_thing)
        self._token_pending: dict[str, set[str]] = {}
        self._token_success_pending: dict[str, set[str]] = {}
        self.game.event_bus.register(
            GameEvent.CHAOS_TOKEN_RESOLVED,
            self._scenario_token_effects,
            priority=TimingPriority.WHEN,
        )
        self.game.event_bus.register(
            GameEvent.SKILL_TEST_FAILED,
            self._scenario_token_fail_effects,
            priority=TimingPriority.AFTER,
        )
        self.game.event_bus.register(
            GameEvent.SKILL_TEST_SUCCESSFUL,
            self._scenario_token_success_effects,
            priority=TimingPriority.AFTER,
        )
        self.game.event_bus.register(
            GameEvent.SKILL_TEST_ENDS,
            self._clear_token_pending,
            priority=TimingPriority.AFTER,
        )

    # ---------------------
    # Helpers
    # ---------------------
    @property
    def s(self):
        return self.game.state.scenario

    @property
    def _is_hard_difficulty(self) -> bool:
        """Hard/Expert 使用剧本参考卡背面（困难/专家）的符号效果。"""
        return str(self.s.vars.get("difficulty", "standard")) in ("hard", "expert")

    @property
    def game_state(self):
        return self.game.state

    def log(self, msg: str) -> None:
        if self.action_log is not None:
            self.action_log.append(msg)

    def set_resolution(self, resolution_id: str, *, message: str = "") -> None:
        self.s.vars["resolution_id"] = resolution_id
        if message:
            self.s.vars["resolution_message"] = message

    def has_treachery(self, treachery_id: str, investigator_id: str = "player") -> bool:
        tre = self.s.vars.get("treacheries", {})
        rec = tre.get(treachery_id)
        return bool(rec and rec.get("investigator_id") == investigator_id)

    def add_treachery(self, treachery_id: str, *, investigator_id: str = "player", attached_to: str | None = None) -> None:
        tre = self.s.vars.setdefault("treacheries", {})
        tre[treachery_id] = {
            "id": treachery_id,
            "investigator_id": investigator_id,
            "attached_to": attached_to,
        }

    def remove_treachery(self, treachery_id: str) -> None:
        tre = self.s.vars.get("treacheries", {})
        tre.pop(treachery_id, None)

    def get_attached(self, treachery_id: str) -> str | None:
        tre = self.s.vars.get("treacheries", {})
        rec = tre.get(treachery_id)
        return rec.get("attached_to") if rec else None

    # ---------------------
    # Location attachments（地点附属卡统一架构）
    # ---------------------
    # 附属到地点的卡（上锁的门、遮蔽迷雾等）以真实 CardInstance 存在：
    # instance.attached_to = location_id，且登记在 LocationState.attachments。
    # 效果查询（调查封锁/隐蔽值加成）统一从附属卡推导，不再散落硬编码。

    def attach_card_to_location(self, card_id: str, location_id: str) -> str | None:
        """Attach a card to a location; returns the new instance_id."""
        from backend.models.state import CardInstance
        loc = self.game_state.get_location(location_id)
        if loc is None:
            return None
        instance_id = self.game_state.next_instance_id()
        ci = CardInstance(
            instance_id=instance_id,
            card_id=card_id,
            owner_id="scenario",
            controller_id="scenario",
            attached_to=location_id,
        )
        self.game_state.cards_in_play[instance_id] = ci
        loc.attachments.append(instance_id)
        return instance_id

    def detach_card_from_location(self, instance_id: str, *, to_encounter_discard: bool = True) -> None:
        """Detach a card from its location and remove it from play."""
        ci = self.game_state.get_card_instance(instance_id)
        if ci is None:
            return
        loc = self.game_state.get_location(ci.attached_to or "")
        if loc is not None and instance_id in loc.attachments:
            loc.attachments.remove(instance_id)
        self.game_state.cards_in_play.pop(instance_id, None)
        if to_encounter_discard:
            self.game_state.scenario.encounter_discard.append(ci.card_id)

    def location_attachment_ids(self, location_id: str) -> list[str]:
        """Card ids attached to a location."""
        loc = self.game_state.get_location(location_id)
        return loc.attachment_card_ids(self.game_state) if loc else []

    def location_attachment_instance(self, location_id: str, card_id: str) -> str | None:
        """Instance id of a specific card attached to a location, if any."""
        loc = self.game_state.get_location(location_id)
        if loc is None:
            return None
        for iid in loc.attachments:
            ci = self.game_state.get_card_instance(iid)
            if ci is not None and ci.card_id == card_id:
                return iid
        return None

    def location_with_attachment(self, card_id: str) -> str | None:
        """First location that has the given card attached."""
        for loc in self.game_state.locations.values():
            if self.location_attachment_instance(loc.location_id, card_id):
                return loc.location_id
        return None

    def location_investigate_blocker(self, location_id: str) -> str | None:
        """card_id of an attachment blocking investigation, if any."""
        if self.location_attachment_instance(location_id, "locked_door"):
            return "locked_door"
        return None

    def location_shroud_bonus(self, location_id: str) -> int:
        """Shroud modifier from attachments (遮蔽迷雾 +2)."""
        bonus = 0
        if self.location_attachment_instance(location_id, "obscuring_fog"):
            bonus += 2
        return bonus

    def _skill_modifiers(self, ctx) -> None:
        # Dreams of R'lyeh: -1 willpower while in play
        if self.has_treachery("dreams_of_r_lyeh", investigator_id=ctx.investigator_id or "player"):
            if ctx.skill_type and getattr(ctx.skill_type, "value", "") == "willpower":
                ctx.modify_amount(-1, "dreams_of_r_lyeh")

    def _on_clue_discovered(self, ctx) -> None:
        # Obscuring Fog discards after attached location is successfully investigated
        loc_id = ctx.location_id
        if not loc_id:
            return
        fog_iid = self.location_attachment_instance(loc_id, "obscuring_fog")
        if fog_iid:
            self.detach_card_from_location(fog_iid)
            self.log("🌫️ 迷雾被驱散（Obscuring Fog弃掉）")

    def _on_enemy_defeated(self, ctx) -> None:
        # Scenario-specific counters
        s = self.s
        if s.scenario_id == "the_midnight_masks":
            # Count cultists defeated (simplified: any enemy in set 'cultists' or known IDs)
            iid = ctx.target
            if iid:
                # Card is already removed from play, so use ctx.extra if present, else ignore
                pass
            s.vars["cultists_defeated"] = int(s.vars.get("cultists_defeated", 0) or 0) + 1
            self.log(f"🕯️ 已击败邪教徒：{s.vars['cultists_defeated']}")

        # Gathering: if Ghoul Priest defeated and act >= 1 -> win
        if s.scenario_id == "the_gathering":
            if ctx.target and ("ghoul_priest" in str(ctx.target)):
                self.set_resolution("R1", message="击败食尸鬼祭司，黎塔助你逃离。")

    def _on_agenda_advanced(self, ctx) -> None:
        s = self.s
        # If agenda advances beyond deck => loss
        if s.current_agenda_index >= len(s.agenda_deck):
            self.set_resolution("R3", message="时间耗尽/密谋达成，调查失败。")

        # Midnight Masks: time is running out (single-agenda scenario)
        if s.scenario_id == "the_midnight_masks":
            self.set_resolution("R4", message="午夜已过，你被迫撤离阿卡姆。")

    # ---------------------
    # Scenario chaos token effects
    # ---------------------
    def _enemy_keyword(self, instance_id: str) -> list[str]:
        inst = self.game.state.get_card_instance(instance_id)
        if inst is None:
            return []
        cd = self.game.state.get_card_data(inst.card_id)
        return list(getattr(cd, "keywords", None) or []) if cd else []

    def _enemies_at(self, location_id: str, keyword: str) -> int:
        loc = self.game.state.get_location(location_id)
        if loc is None:
            return 0
        count = 0
        for iid in loc.enemies:
            if keyword in self._enemy_keyword(iid):
                count += 1
        # 交战敌人也算在该地点
        for inv in self.game.state.investigators.values():
            if inv.location_id != location_id:
                continue
            for iid in inv.threat_area:
                if keyword in self._enemy_keyword(iid):
                    count += 1
        return count

    def _enemies_in_play(self, keyword: str) -> int:
        count = 0
        for iid, inst in self.game.state.cards_in_play.items():
            cd = self.game.state.get_card_data(inst.card_id)
            if cd is None or cd.type.value != "enemy":
                continue
            if keyword in (getattr(cd, "keywords", None) or []):
                count += 1
        return count

    def _max_doom_on_cultists(self) -> int:
        best = 0
        for iid, inst in self.game.state.cards_in_play.items():
            cd = self.game.state.get_card_data(inst.card_id)
            if cd is None or cd.type.value != "enemy":
                continue
            if "cultist" in (getattr(cd, "keywords", None) or []):
                best = max(best, inst.doom)
        return best

    def _total_doom_in_play(self) -> int:
        """场上毁灭标记总数（含密谋上的毁灭）。"""
        total = int(getattr(self.game_state.scenario, "doom_on_agenda", 0) or 0)
        for inst in self.game_state.cards_in_play.values():
            total += getattr(inst, "doom", 0) or 0
        return total

    def _cultists_in_play(self) -> list[str]:
        out = []
        for iid, inst in self.game.state.cards_in_play.items():
            cd = self.game.state.get_card_data(inst.card_id)
            is_cultist = _is_cultist_enemy_id(inst.card_id) or (
                cd is not None and cd.type.value == "enemy"
                and "cultist" in (getattr(cd, "keywords", None) or [])
            )
            if is_cultist:
                out.append(iid)
        return out

    def _nearest_enemy_with(self, inv, keyword: str | None) -> str | None:
        """最近的敌人（交战 > 同地点 > 任意）。"""
        for iid in inv.threat_area:
            if keyword is None or keyword in self._enemy_keyword(iid):
                return iid
        loc = self.game.state.get_location(inv.location_id)
        if loc:
            for iid in loc.enemies:
                if keyword is None or keyword in self._enemy_keyword(iid):
                    return iid
        for iid in self.game.state.cards_in_play:
            inst = self.game.state.get_card_instance(iid)
            cd = self.game.state.get_card_data(inst.card_id) if inst else None
            if cd is None or cd.type.value != "enemy":
                continue
            if keyword is None or keyword in (getattr(cd, "keywords", None) or []):
                return iid
        return None

    def _scenario_token_effects(self, ctx) -> None:
        """Apply scenario-specific symbol token modifiers/effects.

        Values follow the scenario reference card side matching the chosen
        difficulty: Easy/Standard use the front, Hard/Expert use the back.
        """
        from backend.models.enums import ChaosTokenType

        token = ctx.chaos_token
        if token not in (ChaosTokenType.SKULL, ChaosTokenType.CULTIST,
                         ChaosTokenType.TABLET, ChaosTokenType.ELDER_THING):
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        sid = self.s.scenario_id
        hard = self._is_hard_difficulty
        pending = self._token_pending.setdefault(ctx.investigator_id, set())
        success_pending = self._token_success_pending.setdefault(ctx.investigator_id, set())

        if sid in DUNWICH_SCENARIO_IDS:
            self._dunwich_token_effects(ctx, inv, pending, success_pending)
            if ctx.extra.get("token_text"):
                ctx.game_state.log_effect(f"🎲 标记效果：{ctx.extra['token_text']}")
            return

        if sid in CARCOSA_SCENARIO_IDS:
            self._carcosa_token_effects(ctx, inv, pending, success_pending)
            if ctx.extra.get("token_text"):
                ctx.game_state.log_effect(f"🎲 标记效果：{ctx.extra['token_text']}")
            return

        # 循环 3-7：按 campaign 分发到 tokens_{cyc}.apply_token
        cyc = _cycle_for_scenario(sid)
        mod_name = _CYCLE_TOKEN_MODULES.get(cyc)
        if mod_name:
            import importlib
            mod = importlib.import_module(f"backend.scenarios.{mod_name}")
            if mod.apply_token(self, ctx, inv, pending, success_pending):
                if ctx.extra.get("token_text"):
                    ctx.game_state.log_effect(f"🎲 标记效果：{ctx.extra['token_text']}")
            return

        if sid == "the_gathering":
            if token == ChaosTokenType.SKULL:
                if hard:
                    ctx.modify_amount(-2, "gathering_skull_hard")
                    pending.add("gathering_skull_hard_ghoul")
                    ctx.extra["token_text"] = "骷髅 -2，若失败：查找遭遇牌堆/弃牌堆，抽1个食屍鬼敌人"
                else:
                    x = self._enemies_at(inv.location_id, "ghoul")
                    if x:
                        ctx.modify_amount(-x, "gathering_skull")
                    ctx.extra["token_text"] = f"骷髅 -{x}（食屍鬼×{x}）"
            elif token == ChaosTokenType.CULTIST:
                if hard:
                    pending.add("gathering_cultist_horror2")
                    ctx.extra["token_text"] = "异教徒 再揭示1个标记，若失败：受2恐惧"
                    self._reveal_extra_numeric_token(ctx, "gathering_cultist_extra")
                else:
                    ctx.modify_amount(-1, "gathering_cultist")
                    pending.add("gathering_cultist_horror")
                    ctx.extra["token_text"] = "异教徒 -1，若失败受1恐惧"
            elif token == ChaosTokenType.TABLET:
                if hard:
                    ctx.modify_amount(-4, "gathering_tablet_hard")
                    if self._enemies_at(inv.location_id, "ghoul") > 0:
                        inv.damage += 1
                        inv.horror += 1
                        ctx.extra["token_text"] = "石板 -4，地点有食屍鬼：受1伤害1恐惧"
                    else:
                        ctx.extra["token_text"] = "石板 -4"
                else:
                    ctx.modify_amount(-2, "gathering_tablet")
                    if self._enemies_at(inv.location_id, "ghoul") > 0:
                        inv.damage += 1
                        ctx.extra["token_text"] = "石板 -2，地点有食屍鬼：受1伤害"
                    else:
                        ctx.extra["token_text"] = "石板 -2"

        elif sid == "the_midnight_masks":
            if token == ChaosTokenType.SKULL:
                if hard:
                    x = self._total_doom_in_play()
                    if x:
                        ctx.modify_amount(-x, "midnight_skull_hard")
                    ctx.extra["token_text"] = f"骷髅 -{x}（场上毁灭总数×{x}）"
                else:
                    x = self._max_doom_on_cultists()
                    if x:
                        ctx.modify_amount(-x, "midnight_skull")
                    ctx.extra["token_text"] = f"骷髅 -{x}（异教徒最多毁灭×{x}）"
            elif token == ChaosTokenType.CULTIST:
                if hard:
                    ctx.modify_amount(-2, "midnight_cultist_hard")
                    cultists = self._cultists_in_play()
                    if cultists:
                        for iid in cultists:
                            inst = self.game.state.get_card_instance(iid)
                            if inst is not None:
                                inst.doom += 1
                        ctx.extra["token_text"] = f"异教徒 -2，场上{len(cultists)}个异教徒各+1毁灭"
                    else:
                        ctx.extra["token_text"] = "异教徒 -2，场上无异教徒"
                        self._reveal_extra_numeric_token(ctx, "midnight_cultist_extra")
                else:
                    ctx.modify_amount(-2, "midnight_cultist")
                    target = self._find_nearest_cultist(inv.location_id)
                    if target:
                        inst = self.game.state.get_card_instance(target)
                        if inst is not None:
                            inst.doom += 1
                    ctx.extra["token_text"] = "异教徒 -2，最近异教徒+1毁灭"
            elif token == ChaosTokenType.TABLET:
                if hard:
                    ctx.modify_amount(-4, "midnight_tablet_hard")
                    pending.add("midnight_tablet_clues_all")
                    ctx.extra["token_text"] = "石板 -4，若失败：将你所有线索放到所在地点"
                else:
                    ctx.modify_amount(-3, "midnight_tablet")
                    pending.add("midnight_tablet_clue")
                    ctx.extra["token_text"] = "石板 -3，若失败：放1线索到地点"

        elif sid == "the_devourer_below":
            if token == ChaosTokenType.SKULL:
                if hard:
                    ctx.modify_amount(-3, "devourer_skull_hard")
                    pending.add("devourer_skull_hard_monster")
                    ctx.extra["token_text"] = "骷髅 -3，若失败：查找遭遇牌堆/弃牌堆，抽1个怪物敌人"
                else:
                    x = self._enemies_in_play("monster")
                    if x:
                        ctx.modify_amount(-x, "devourer_skull")
                    ctx.extra["token_text"] = f"骷髅 -{x}（怪物×{x}）"
            elif token == ChaosTokenType.CULTIST:
                if hard:
                    ctx.modify_amount(-4, "devourer_cultist_hard")
                    target = self._nearest_enemy_with(inv, None)
                    if target:
                        inst = self.game.state.get_card_instance(target)
                        if inst is not None:
                            inst.doom += 2
                    ctx.extra["token_text"] = "异教徒 -4，最近敌人+2毁灭"
                else:
                    ctx.modify_amount(-2, "devourer_cultist")
                    target = self._nearest_enemy_with(inv, None)
                    if target:
                        inst = self.game.state.get_card_instance(target)
                        if inst is not None:
                            inst.doom += 1
                    ctx.extra["token_text"] = "异教徒 -2，最近敌人+1毁灭"
            elif token == ChaosTokenType.TABLET:
                if hard:
                    ctx.modify_amount(-5, "devourer_tablet_hard")
                    if self._enemies_at(inv.location_id, "monster") > 0:
                        inv.damage += 1
                        inv.horror += 1
                        ctx.extra["token_text"] = "石板 -5，地点有怪物：受1伤害1恐惧"
                    else:
                        ctx.extra["token_text"] = "石板 -5"
                else:
                    ctx.modify_amount(-3, "devourer_tablet")
                    if self._enemies_at(inv.location_id, "monster") > 0:
                        inv.damage += 1
                        ctx.extra["token_text"] = "石板 -3，地点有怪物：受1伤害"
                    else:
                        ctx.extra["token_text"] = "石板 -3"
            elif token == ChaosTokenType.ELDER_THING:
                base = -7 if hard else -5
                ctx.modify_amount(base, "devourer_elder_thing")
                text = f"古老存在 {base}"
                if self._enemies_in_play("ancient_one") > 0:
                    # 再揭示1个标记（只取数值修正，不再触发符号效果）
                    extra_token = self.game.chaos_bag.draw()
                    from backend.models.enums import CHAOS_TOKEN_VALUES
                    extra_val = CHAOS_TOKEN_VALUES.get(extra_token) or 0
                    ctx.modify_amount(extra_val, "devourer_elder_thing_extra")
                    text += f"，古神在场：再揭示[{getattr(extra_token, 'value', extra_token)}]"
                ctx.extra["token_text"] = text

        # 记录符号标记的场景效果到行动日志
        if ctx.extra.get("token_text"):
            ctx.game_state.log_effect(f"🎲 标记效果：{ctx.extra['token_text']}")

    # ---------------------
    # Dunwich Legacy token effects (Standard values)
    # ---------------------
    def _enemy_card_at(self, location_id: str, card_id: str) -> bool:
        loc = self.game_state.get_location(location_id)
        if loc is None:
            return False
        for iid in loc.enemies:
            inst = self.game_state.get_card_instance(iid)
            if inst is not None and inst.card_id == card_id:
                return True
        # 交战敌人也算在该地点（遍历所有调查员的威胁区）
        for inv in self.game_state.investigators.values():
            if inv.location_id != location_id:
                continue
            for iid in inv.threat_area:
                inst = self.game_state.get_card_instance(iid)
                if inst is not None and inst.card_id == card_id:
                    return True
        return False

    def _enemy_card_in_play(self, card_id: str) -> bool:
        for iid, inst in self.game_state.cards_in_play.items():
            if inst.card_id == card_id:
                return True
        return False

    def _location_has_trait(self, location_id: str, trait: str) -> bool:
        loc = self.game_state.get_location(location_id)
        if loc is None or loc.card_data is None:
            return False
        return trait in (loc.card_data.traits or [])

    def _count_locations_with_trait(self, trait: str) -> int:
        return sum(1 for loc in self.game_state.locations.values()
                   if loc.card_data and trait in (loc.card_data.traits or []))

    def _discard_top_of_deck(self, inv, n: int) -> list[str]:
        out = []
        for _ in range(min(n, len(inv.deck))):
            cid = inv.deck.pop(0)
            inv.discard.append(cid)
            out.append(cid)
        return out

    def _printed_cost_sum(self, card_ids: list[str]) -> int:
        total = 0
        for cid in card_ids:
            cd = self.game_state.get_card_data(cid)
            if cd is not None:
                total += cd.cost or 0
        return total

    def _reveal_extra_numeric_token(self, ctx, reason: str) -> None:
        """再揭示1个标记（只取数值修正，不递归触发符号效果）。"""
        from backend.models.enums import CHAOS_TOKEN_VALUES
        extra = self.game.chaos_bag.draw()
        val = CHAOS_TOKEN_VALUES.get(extra) or 0
        ctx.modify_amount(val, reason)
        ctx.extra["token_text"] = (
            f"{ctx.extra.get('token_text', '')}，再揭示[{getattr(extra, 'value', extra)}]"
        )

    def _dunwich_token_effects(self, ctx, inv, pending, success_pending) -> None:
        """敦威治遗产 8 章符号效果（按难度取参考卡正面/背面数值）。

        简化项（已在代码注释标明）：选择类效果自动取对玩家最有利/最常用分支；
        技能卡图标无效化、地点移除、Brood 线索移除等未实现。
        """
        from backend.models.enums import ChaosTokenType

        token = ctx.chaos_token
        sid = self.s.scenario_id
        hard = self._is_hard_difficulty

        if sid == "extracurricular_activity":
            if token == ChaosTokenType.SKULL:
                if hard:
                    ctx.modify_amount(-2, "eca_skull_hard")
                    pending.add("eca_skull_deck5")
                    ctx.extra["token_text"] = "骷髅 -2，若失败：弃牌堆顶5张"
                else:
                    ctx.modify_amount(-1, "eca_skull")
                    pending.add("eca_skull_deck3")
                    ctx.extra["token_text"] = "骷髅 -1，若失败：弃牌堆顶3张"
            elif token == ChaosTokenType.CULTIST:
                high = 5 if hard else 3
                x = high if len(inv.discard) >= 10 else 1
                ctx.modify_amount(-x, "eca_cultist")
                ctx.extra["token_text"] = f"异教徒 -{x}" + (f"（弃牌堆≥10张，改为-{high}）" if x == high else "")
            elif token == ChaosTokenType.ELDER_THING:
                n = 3 if hard else 2
                discarded = self._discard_top_of_deck(inv, n)
                x = self._printed_cost_sum(discarded)
                ctx.modify_amount(-x, "eca_elder_thing")
                ctx.extra["token_text"] = f"旧神之物 -{x}（弃牌堆顶{n}张费用和）"

        elif sid == "the_house_always_wins":
            if token == ChaosTokenType.SKULL:
                # 简化：资源足够时自动花资源视为0（对玩家有利的常规选择）
                cost = 3 if hard else 2
                if inv.resources >= cost:
                    inv.resources -= cost
                    ctx.extra["token_text"] = f"骷髅 视为0（花费{cost}资源）"
                else:
                    ctx.modify_amount(-3 if hard else -2, "thaw_skull")
                    ctx.extra["token_text"] = f"骷髅 {-3 if hard else -2}"
            elif token == ChaosTokenType.CULTIST:
                ctx.modify_amount(-3, "thaw_cultist")
                if hard:
                    pending.add("thaw_cultist_hard_lose3")
                    ctx.extra["token_text"] = "异教徒 -3，若失败：失去3资源"
                else:
                    success_pending.add("thaw_cultist_gain3")
                    ctx.extra["token_text"] = "异教徒 -3，若成功：获得3资源"
            elif token == ChaosTokenType.TABLET:
                ctx.modify_amount(-2, "thaw_tablet")
                if hard:
                    inv.resources = max(0, inv.resources - 3)
                    ctx.extra["token_text"] = "石板 -2，失去3资源"
                else:
                    pending.add("thaw_tablet_lose3")
                    ctx.extra["token_text"] = "石板 -2，若失败：失去3资源"

        elif sid == "the_miskatonic_museum":
            if token == ChaosTokenType.SKULL:
                same_loc = self._enemy_card_at(inv.location_id, "hunting_horror")
                x = (4 if same_loc else 2) if hard else (3 if same_loc else 1)
                ctx.modify_amount(-x, "tmm_skull")
                ctx.extra["token_text"] = f"骷髅 -{x}" + ("（与追獵恐魔同地点）" if same_loc else "")
            elif token == ChaosTokenType.CULTIST:
                ctx.modify_amount(-3 if hard else -1, "tmm_cultist")
                pending.add("tmm_cultist_spawn_horror")
                ctx.extra["token_text"] = f"异教徒 {-3 if hard else -1}，若失败：追獵恐魔生成在你所在地"
            elif token == ChaosTokenType.TABLET:
                if hard:
                    ctx.modify_amount(-4, "tmm_tablet_hard")
                    if self._enemy_card_at(inv.location_id, "hunting_horror"):
                        cd = self.game_state.get_card_data("hunting_horror")
                        if cd is not None:
                            inv.damage += cd.enemy_damage or 0
                            inv.horror += cd.enemy_horror or 0
                        ctx.extra["token_text"] = "石板 -4，同地点追獵恐魔立刻攻击你"
                    else:
                        ctx.extra["token_text"] = "石板 -4"
                else:
                    ctx.modify_amount(-2, "tmm_tablet")
                    pending.add("tmm_tablet_return_clue")
                    ctx.extra["token_text"] = "石板 -2：将你的1个线索放回所在地点"
            elif token == ChaosTokenType.ELDER_THING:
                ctx.modify_amount(-5 if hard else -3, "tmm_elder_thing")
                pending.add("tmm_elder_discard_asset")
                ctx.extra["token_text"] = f"旧神之物 {-5 if hard else -3}，若失败：弃1张你控制的支援"

        elif sid == "essex_county_express":
            if token == ChaosTokenType.SKULL:
                x = (self.s.current_agenda_index or 0) + (2 if hard else 1)
                ctx.modify_amount(-x, "ece_skull")
                ctx.extra["token_text"] = f"骷髅 -{x}（当前密谋编号{'+1' if hard else ''}）"
            elif token == ChaosTokenType.CULTIST:
                if hard:
                    pending.add("ece_cultist_lose_actions")
                    ctx.extra["token_text"] = "异教徒 再揭示1个标记，若失败且是你的回合：失去剩余行动"
                    self._reveal_extra_numeric_token(ctx, "ece_cultist_extra")
                else:
                    ctx.modify_amount(-1, "ece_cultist")
                    pending.add("ece_cultist_lose_actions")
                    ctx.extra["token_text"] = "异教徒 -1，若失败且是你的回合：失去剩余行动"
            elif token == ChaosTokenType.TABLET:
                if hard:
                    ctx.modify_amount(-4, "ece_tablet_hard")
                    cultists = self._cultists_in_play()
                    for iid in cultists:
                        inst = self.game.state.get_card_instance(iid)
                        if inst is not None:
                            inst.doom += 1
                    ctx.extra["token_text"] = f"石板 -4，场上{len(cultists)}个异教徒各+1毁灭"
                else:
                    ctx.modify_amount(-2, "ece_tablet")
                    target = self._find_nearest_cultist(inv.location_id)
                    if target:
                        inst = self.game_state.get_card_instance(target)
                        if inst is not None:
                            inst.doom += 1
                    ctx.extra["token_text"] = "石板 -2：最近异教徒+1毁灭"
            elif token == ChaosTokenType.ELDER_THING:
                ctx.modify_amount(-3, "ece_elder_thing")
                if hard:
                    pending.add("ece_elder_discard_hand_margin")
                    ctx.extra["token_text"] = "旧神之物 -3，若失败：每低于难度1点弃1张手牌"
                else:
                    pending.add("ece_elder_discard_hand")
                    ctx.extra["token_text"] = "旧神之物 -3，若失败：弃1张手牌"

        elif sid == "blood_on_the_altar":
            if token == ChaosTokenType.SKULL:
                # 简化：以“无线索地点”近似“底下无遭遇卡的地点”（该机制未实现）
                n = sum(1 for loc in self.game_state.locations.values() if loc.clues == 0)
                x = n if hard else min(4, n)
                if x:
                    ctx.modify_amount(-x, "bota_skull")
                ctx.extra["token_text"] = f"骷髅 -{x}（无遭遇卡地点×{x}" + ("）" if hard else "，最大4）")
            elif token == ChaosTokenType.CULTIST:
                ctx.modify_amount(-4 if hard else -2, "bota_cultist")
                pending.add("bota_cultist_clue_to_loc")
                ctx.extra["token_text"] = f"异教徒 {-4 if hard else -2}，若失败：供应堆放1线索到所在地点"
            elif token == ChaosTokenType.TABLET:
                if hard:
                    ctx.modify_amount(-3, "bota_tablet_hard")
                    ctx.extra["token_text"] = "石板 -3"
                    self._reveal_extra_numeric_token(ctx, "bota_tablet_extra")
                else:
                    ctx.modify_amount(-2, "bota_tablet")
                    ctx.extra["token_text"] = "石板 -2"
                    if "隐藏密室" in (self.game_state.get_location(inv.location_id).card_data.name_cn
                                      if self.game_state.get_location(inv.location_id) else "") \
                            or self._location_has_trait(inv.location_id, "密室"):
                        self._reveal_extra_numeric_token(ctx, "bota_tablet_extra")
            elif token == ChaosTokenType.ELDER_THING:
                ctx.modify_amount(-3, "bota_elder_thing")
                if hard:
                    ctx.game_state.scenario.doom_on_agenda += 1
                    self._check_agenda_threshold()
                    ctx.extra["token_text"] = "旧神之物 -3，当前密谋+1毁灭"
                else:
                    pending.add("bota_elder_doom_agenda")
                    ctx.extra["token_text"] = "旧神之物 -3，若失败：当前密谋+1毁灭"

        elif sid == "undimensioned_and_unseen":
            if token == ChaosTokenType.SKULL:
                per = 2 if hard else 1
                count = self._enemy_keyword_count_in_play("brood_of_yog_sothoth")
                x = per * count
                if x:
                    ctx.modify_amount(-x, "uau_skull")
                ctx.extra["token_text"] = f"骷髅 -{x}（猶格·索托斯之子×{count}，每只-{per}）"
            elif token == ChaosTokenType.CULTIST:
                if hard:
                    ctx.extra["token_text"] = "异教徒 再揭示1个标记，若失败：受1伤害1恐惧"
                    pending.add("uau_cultist_hard_dh")
                else:
                    ctx.extra["token_text"] = "异教徒 再揭示1个标记，若失败：受1恐惧"
                    pending.add("uau_cultist_horror")
                self._reveal_extra_numeric_token(ctx, "uau_cultist_extra")
            elif token == ChaosTokenType.TABLET:
                if hard:
                    # 简化：Brood 线索机制未实现，固定取自动失败分支
                    ctx.extra["force_auto_fail"] = True
                    ctx.extra["token_text"] = "石板 自动失败（简化：未实现移除Brood线索的选项）"
                else:
                    # 简化：Brood 线索机制未实现，固定视为 -4
                    ctx.modify_amount(-4, "uau_tablet")
                    ctx.extra["token_text"] = "石板 -4（简化：未实现移除Brood线索的选项）"
            elif token == ChaosTokenType.ELDER_THING:
                ctx.modify_amount(-5 if hard else -3, "uau_elder_thing")
                pending.add("uau_elder_brood_attack")
                ctx.extra["token_text"] = f"旧神之物 {-5 if hard else -3}（对抗Brood时它立刻攻击你）"

        elif sid == "where_doom_awaits":
            if token == ChaosTokenType.SKULL:
                in_phantasm = self._location_has_trait(inv.location_id, "幻境")
                x = (5 if in_phantasm else 2) if hard else (3 if in_phantasm else 1)
                ctx.modify_amount(-x, "wda_skull")
                ctx.extra["token_text"] = f"骷髅 -{x}" + ("（幻境地点）" if in_phantasm else "")
            elif token == ChaosTokenType.CULTIST:
                # 简化：技能卡图标/效果无效化未实现，仅再揭示标记
                ctx.extra["token_text"] = "异教徒 再揭示1个标记（简化：图标无效化未实现）"
                self._reveal_extra_numeric_token(ctx, "wda_cultist_extra")
            elif token == ChaosTokenType.TABLET:
                if hard:
                    if (self.s.current_agenda_index or 0) == 1:
                        ctx.extra["force_auto_fail"] = True
                        ctx.extra["token_text"] = "石板 自动失败（密谋2）"
                    else:
                        ctx.modify_amount(-3, "wda_tablet_hard")
                        ctx.extra["token_text"] = "石板 -3"
                else:
                    x = 4 if (self.s.current_agenda_index or 0) == 1 else 2
                    ctx.modify_amount(-x, "wda_tablet")
                    ctx.extra["token_text"] = f"石板 -{x}" + ("（密谋2）" if x == 4 else "")
            elif token == ChaosTokenType.ELDER_THING:
                n = 3 if hard else 2
                discarded = self._discard_top_of_deck(inv, n)
                x = self._printed_cost_sum(discarded)
                ctx.modify_amount(-x, "wda_elder_thing")
                ctx.extra["token_text"] = f"旧神之物 -{x}（弃牌堆顶{n}张费用和）"

        elif sid == "lost_in_time_and_space":
            if token == ChaosTokenType.SKULL:
                n = self._count_locations_with_trait("異次元")
                x = n if hard else min(5, n)
                if x:
                    ctx.modify_amount(-x, "lits_skull")
                ctx.extra["token_text"] = f"骷髅 -{x}（異次元地点×{x}" + ("）" if hard else "，最大5）")
            elif token == ChaosTokenType.CULTIST:
                ctx.extra["token_text"] = "异教徒 再揭示1个标记，若失败：穿越到遭遇地点"
                pending.add("lits_cultist_move_location")
                self._reveal_extra_numeric_token(ctx, "lits_cultist_extra")
            elif token == ChaosTokenType.TABLET:
                ctx.modify_amount(-5 if hard else -3, "lits_tablet")
                pending.add("lits_tablet_yog_attack")
                ctx.extra["token_text"] = f"石板 {-5 if hard else -3}（猶格·索托斯在场时它立刻攻击你）"
            elif token == ChaosTokenType.ELDER_THING:
                loc = self.game_state.get_location(inv.location_id)
                shroud = loc.shroud if loc else 0
                x = shroud * 2 if hard else shroud
                ctx.modify_amount(-x, "lits_elder_thing")
                ctx.extra["token_text"] = f"旧神之物 -{x}（所在地点隐藏值{'×2' if hard else ''}）"

    def _enemy_keyword_count_in_play(self, card_id: str) -> int:
        return sum(1 for inst in self.game_state.cards_in_play.values()
                   if inst.card_id == card_id)

    # ---------------------
    # Path to Carcosa token effects (按难度取参考卡正面/背面)
    # ---------------------
    def _enemies_with_keyword_in_play(self, keyword: str) -> list[str]:
        out = []
        for iid, inst in self.game_state.cards_in_play.items():
            cd = self.game_state.get_card_data(inst.card_id)
            if cd is not None and cd.type.value == "enemy" \
                    and keyword in (getattr(cd, "keywords", None) or []):
                out.append(iid)
        return out

    def _total_doom_on_enemies(self) -> int:
        total = 0
        for inst in self.game_state.cards_in_play.values():
            cd = self.game_state.get_card_data(inst.card_id)
            if cd is not None and cd.type.value == "enemy":
                total += getattr(inst, "doom", 0) or 0
        return total

    def _max_doom_on_enemies(self) -> int:
        best = 0
        for iid, inst in self.game_state.cards_in_play.items():
            cd = self.game_state.get_card_data(inst.card_id)
            if cd is not None and cd.type.value == "enemy":
                best = max(best, getattr(inst, "doom", 0) or 0)
        return best

    def _bfs_distance(self, from_location_id: str, to_location_id: str) -> int:
        """Shortest-path distance over the location connection graph."""
        if from_location_id == to_location_id:
            return 0
        visited = {from_location_id}
        frontier = [from_location_id]
        dist = 0
        while frontier:
            dist += 1
            nxt = []
            for lid in frontier:
                loc = self.game_state.get_location(lid)
                if loc is None:
                    continue
                for conn in loc.connections:
                    if conn == to_location_id:
                        return dist
                    if conn not in visited:
                        visited.add(conn)
                        nxt.append(conn)
            frontier = nxt
        return 0

    def _byakhee_move_step(self) -> None:
        """每个未交战的拜亚基朝最近的调查员移动一次（简化：沿 BFS 走一步）。"""
        from collections import deque
        inv_locs = {inv.location_id for inv in self.game_state.investigators.values()
                    if not inv.is_defeated}
        for loc in self.game_state.locations.values():
            for eid in list(loc.enemies):
                inst = self.game_state.get_card_instance(eid)
                cd = self.game_state.get_card_data(inst.card_id) if inst else None
                if cd is None or "byakhee" not in (cd.keywords or []):
                    continue
                # BFS 找最近调查员方向的下一步
                queue = deque([(loc.location_id, None)])
                visited = {loc.location_id}
                hop = None
                while queue:
                    cur, first = queue.popleft()
                    if cur in inv_locs:
                        hop = first
                        break
                    cur_loc = self.game_state.get_location(cur)
                    for conn in (cur_loc.connections if cur_loc else []):
                        if conn not in visited:
                            visited.add(conn)
                            queue.append((conn, first or conn))
                if hop:
                    dest = self.game_state.get_location(hop)
                    if dest is not None:
                        loc.enemies.remove(eid)
                        dest.enemies.append(eid)

    def _carcosa_token_effects(self, ctx, inv, pending, success_pending) -> None:
        """卡尔克萨之路 8 章符号效果（按难度取参考卡正面/背面数值）。

        简化项（代码内注明）：Act 多版本、密谋毁灭只追踪当前密谋、
        技能卡图标无效化未实现等。
        """
        from backend.models.enums import ChaosTokenType

        token = ctx.chaos_token
        sid = self.s.scenario_id
        hard = self._is_hard_difficulty
        loc = self.game_state.get_location(inv.location_id)

        if sid == "curtain_call":
            if token == ChaosTokenType.SKULL:
                if hard:
                    x = max(1, inv.horror)
                    ctx.modify_amount(-x, "cc_skull_hard")
                    ctx.extra["token_text"] = f"骷髅 -{x}（你身上的恐惧数，至少1）"
                else:
                    x = 3 if inv.horror >= 3 else 1
                    ctx.modify_amount(-x, "cc_skull")
                    ctx.extra["token_text"] = f"骷髅 -{x}" + ("（身上恐惧≥3）" if x == 3 else "")
            else:  # cultist / tablet / elder_thing 同文
                v = 5 if hard else 4
                ctx.modify_amount(-v, f"cc_{token.value}")
                if loc is not None and loc.horror >= 1:
                    inv.horror += 1
                    ctx.extra["token_text"] = f"{token.value} -{v}，地点有恐惧：你受1恐惧"
                elif loc is not None:
                    loc.horror += 1
                    ctx.extra["token_text"] = f"{token.value} -{v}，地点无恐惧：放置1恐惧于地点"
                else:
                    ctx.extra["token_text"] = f"{token.value} -{v}"

        elif sid == "the_last_king":
            if token == ChaosTokenType.SKULL:
                pending.add("tlk_skull_possessed_doom")
                ctx.extra["token_text"] = "骷髅 再揭示1个标记，若失败：场上1个附身敌人+1毁灭"
                self._reveal_extra_numeric_token(ctx, "tlk_skull_extra")
            elif token == ChaosTokenType.CULTIST:
                if hard:
                    ctx.modify_amount(-3, "tlk_cultist_hard")
                    if inv.clues > 0:
                        inv.clues -= 1
                        if loc is not None:
                            loc.clues += 1
                    ctx.extra["token_text"] = "异教徒 -3，将你的1个线索放到所在地点"
                else:
                    ctx.modify_amount(-2, "tlk_cultist")
                    pending.add("tlk_cultist_clue")
                    ctx.extra["token_text"] = "异教徒 -2，若失败：将你的1个线索放到所在地点"
            elif token == ChaosTokenType.TABLET:
                ctx.modify_amount(-4, "tlk_tablet")
                if hard:
                    inv.horror += 1
                    ctx.extra["token_text"] = "石板 -4，受1恐惧"
                else:
                    pending.add("tlk_tablet_horror")
                    ctx.extra["token_text"] = "石板 -4，若失败：受1恐惧"
            elif token == ChaosTokenType.ELDER_THING:
                x = loc.shroud if loc else 0
                ctx.modify_amount(-x, "tlk_elder_thing")
                if hard:
                    pending.add("tlk_elder_damage")
                    ctx.extra["token_text"] = f"旧神之物 -{x}（地点隐藏值），若失败：受1伤害"
                else:
                    ctx.extra["token_text"] = f"旧神之物 -{x}（地点隐藏值）"

        elif sid == "echoes_of_the_past":
            if token == ChaosTokenType.SKULL:
                if hard:
                    x = self._total_doom_on_enemies()
                    ctx.extra["token_text"] = f"骷髅 -{x}（场上敌人毁灭总数）"
                else:
                    x = self._max_doom_on_enemies()
                    ctx.extra["token_text"] = f"骷髅 -{x}（场上单个敌人最多毁灭）"
                if x:
                    ctx.modify_amount(-x, "eotp_skull")
            elif token == ChaosTokenType.CULTIST:
                if hard:
                    ctx.modify_amount(-4, "eotp_cultist_hard")
                    target = self._nearest_enemy_with(inv, None)
                    if target:
                        inst = self.game_state.get_card_instance(target)
                        if inst is not None:
                            inst.doom += 1
                    ctx.extra["token_text"] = "异教徒 -4，最近敌人+1毁灭"
                else:
                    ctx.modify_amount(-2, "eotp_cultist")
                    pending.add("eotp_cultist_doom")
                    ctx.extra["token_text"] = "异教徒 -2，若失败：最近敌人+1毁灭"
            elif token == ChaosTokenType.TABLET:
                if hard:
                    ctx.modify_amount(-4, "eotp_tablet_hard")
                    self._random_discard_from_hand(inv)
                    ctx.extra["token_text"] = "石板 -4，随机弃1手牌"
                else:
                    ctx.modify_amount(-2, "eotp_tablet")
                    pending.add("eotp_tablet_discard")
                    ctx.extra["token_text"] = "石板 -2，若失败：随机弃1手牌"
            elif token == ChaosTokenType.ELDER_THING:
                v = 4 if hard else 2
                ctx.modify_amount(-v, "eotp_elder_thing")
                has_enemy = bool(loc and loc.enemies) or bool(inv.threat_area)
                if hard:
                    if has_enemy:
                        inv.horror += 1
                        ctx.extra["token_text"] = f"旧神之物 -{v}，地点有敌人：受1恐惧"
                    else:
                        ctx.extra["token_text"] = f"旧神之物 -{v}"
                else:
                    if has_enemy:
                        pending.add("eotp_elder_horror")
                    ctx.extra["token_text"] = f"旧神之物 -{v}" + ("，若失败：受1恐惧" if has_enemy else "")

        elif sid == "the_unspeakable_oath":
            if token == ChaosTokenType.SKULL:
                if hard:
                    pending.add("tuo_skull_monster_under")
                    ctx.extra["token_text"] = "骷髅 再揭示1个标记，若失败：搁置怪物置于剧本牌堆下"
                    self._reveal_extra_numeric_token(ctx, "tuo_skull_extra")
                else:
                    ctx.modify_amount(-1, "tuo_skull")
                    pending.add("tuo_skull_monster_under")
                    ctx.extra["token_text"] = "骷髅 -1，若失败：搁置怪物置于剧本牌堆下（每次检定限1次）"
            elif token == ChaosTokenType.CULTIST:
                x = inv.horror
                ctx.modify_amount(-x, "tuo_cultist")
                if hard:
                    pending.add("tuo_symbol_horror")
                ctx.extra["token_text"] = f"异教徒 -{x}（你身上的恐惧数）" + ("，若失败：受1恐惧" if hard else "")
            elif token == ChaosTokenType.TABLET:
                x = loc.shroud if loc else 0
                ctx.modify_amount(-x, "tuo_tablet")
                if hard:
                    pending.add("tuo_symbol_horror")
                ctx.extra["token_text"] = f"石板 -{x}（地点基础隐藏值）" + ("，若失败：受1恐惧" if hard else "")
            elif token == ChaosTokenType.ELDER_THING:
                # 简化：固定取"搁置怪物置于剧本牌堆下"分支（自动失败分支不利，理性玩家不选）
                moved = self._set_aside_monster_under_scenario()
                ctx.extra["token_text"] = "旧神之物 0" + ("，搁置怪物置于剧本牌堆下" if moved else "")

        elif sid == "a_phantom_of_truth":
            if token == ChaosTokenType.SKULL:
                total = self._total_doom_in_play()
                x = total if hard else min(5, total)
                if x:
                    ctx.modify_amount(-x, "apot_skull")
                ctx.extra["token_text"] = f"骷髅 -{x}（场上毁灭数" + ("）" if hard else "，最多5）")
            elif token == ChaosTokenType.CULTIST:
                ctx.modify_amount(-2, "apot_cultist")
                if hard:
                    self._byakhee_move_step()
                    ctx.extra["token_text"] = "异教徒 -2，未交战拜亚基朝最近调查员移动"
                else:
                    pending.add("apot_cultist_byakhee")
                    ctx.extra["token_text"] = "异教徒 -2，若失败：未交战拜亚基朝最近调查员移动"
            elif token == ChaosTokenType.TABLET:
                # 简化：技能卡图标/效果无效化未实现（同 wda 异教徒）
                v = 4 if hard else 3
                ctx.modify_amount(-v, "apot_tablet")
                ctx.extra["token_text"] = f"石板 -{v}（简化：投入技能卡图标无效化未实现）"
            elif token == ChaosTokenType.ELDER_THING:
                v = 3 if hard else 2
                ctx.modify_amount(-v, "apot_elder_thing")
                pending.add("apot_elder_resources")
                ctx.extra["token_text"] = f"旧神之物 -{v}，若失败：每低于难度1点失去1资源"

        elif sid == "the_pallid_mask":
            if token == ChaosTokenType.SKULL:
                start = self.s.vars.get("start_location") or self.s.vars.get("central_location") or inv.location_id
                dist = self._bfs_distance(inv.location_id, start)
                x = dist if hard else min(5, dist)
                if x:
                    ctx.modify_amount(-x, "tpm_skull")
                ctx.extra["token_text"] = f"骷髅 -{x}（距起始地点距离" + ("）" if hard else "，最多5）")
            elif token == ChaosTokenType.CULTIST:
                v = 3 if hard else 2
                ctx.modify_amount(-v, "tpm_cultist")
                if ctx.skill_type is not None and ctx.skill_type.value == "combat":
                    success_pending.add("tpm_cultist_no_damage_hard" if hard else "tpm_cultist_less_damage")
                    ctx.extra["token_text"] = f"异教徒 -{v}，若攻击成功：" + ("本次攻击不造成伤害" if hard else "本次攻击伤害-1")
                else:
                    ctx.extra["token_text"] = f"异教徒 -{v}"
            elif token == ChaosTokenType.TABLET:
                v = 3 if hard else 2
                ctx.modify_amount(-v, "tpm_tablet")
                attacker = self._ready_ghoul_or_specter_at(inv.location_id, ready=hard)
                if attacker:
                    cd = self.game_state.get_card_data(attacker.card_id)
                    if cd is not None:
                        inv.damage += cd.enemy_damage or 0
                        inv.horror += cd.enemy_horror or 0
                    ctx.extra["token_text"] = f"石板 -{v}，地点的食屍鬼/灵怪" + ("准备并攻击你" if hard else "攻击你")
                else:
                    ctx.extra["token_text"] = f"石板 -{v}"
            elif token == ChaosTokenType.ELDER_THING:
                v = 4 if hard else 3
                ctx.modify_amount(-v, "tpm_elder_thing")
                pending.add("tpm_elder_pull_ghoul")
                ctx.extra["token_text"] = f"旧神之物 -{v}，若失败：从遭遇牌堆/弃牌堆抽1个食屍鬼或灵怪敌人"

        elif sid == "black_stars_rise":
            if token == ChaosTokenType.SKULL:
                # 简化：引擎只追踪当前密谋的毁灭
                x = int(getattr(self.s, "doom_on_agenda", 0) or 0)
                if x:
                    ctx.modify_amount(-x, "bsr_skull")
                ctx.extra["token_text"] = f"骷髅 -{x}（当前密谋毁灭数）"
            elif token == ChaosTokenType.CULTIST:
                doomed = self._doomed_enemy_near(inv)
                if doomed:
                    ctx.extra["force_auto_fail"] = True
                    ctx.extra["token_text"] = "异教徒 再揭示1个标记，附近有带毁灭敌人：自动失败"
                else:
                    ctx.extra["token_text"] = "异教徒 再揭示1个标记"
                self._reveal_extra_numeric_token(ctx, "bsr_cultist_extra")
            elif token == ChaosTokenType.TABLET:
                pending.add("bsr_tablet_doom")
                ctx.extra["token_text"] = "石板 再揭示1个标记，若失败：当前密谋+1毁灭"
                self._reveal_extra_numeric_token(ctx, "bsr_tablet_extra")
            elif token == ChaosTokenType.ELDER_THING:
                v = 3 if hard else 2
                ctx.modify_amount(-v, "bsr_elder_thing")
                pending.add("bsr_elder_pull_byakhee")
                ctx.extra["token_text"] = f"旧神之物 -{v}，若失败：从遭遇牌堆/弃牌堆抽1个拜亚基敌人"

        elif sid == "dim_carcosa":
            if token == ChaosTokenType.SKULL:
                if hard:
                    x = inv.horror
                    ctx.modify_amount(-x, "dc_skull_hard")
                    ctx.extra["token_text"] = f"骷髅 -{x}（你身上的恐惧数）"
                else:
                    x = 4 if (inv.sanity - inv.horror) <= 0 else 2
                    ctx.modify_amount(-x, "dc_skull")
                    ctx.extra["token_text"] = f"骷髅 -{x}" + ("（神智归零）" if x == 4 else "")
            elif token == ChaosTokenType.CULTIST:
                pending.add("dc_cultist_horror2" if hard else "dc_cultist_horror1")
                ctx.extra["token_text"] = f"异教徒 再揭示1个标记，若失败：受{2 if hard else 1}恐惧"
                self._reveal_extra_numeric_token(ctx, "dc_cultist_extra")
            elif token == ChaosTokenType.TABLET:
                v = 5 if hard else 3
                ctx.modify_amount(-v, "dc_tablet")
                hastur = any(iid.startswith("hastur") or (self.game_state.get_card_instance(iid) and (self.game_state.get_card_instance(iid).card_id or "").startswith("hastur"))
                             for iid in self.game_state.cards_in_play)
                if hastur:
                    pending.add("dc_tablet_clue")
                    ctx.extra["token_text"] = f"石板 -{v}，若失败且哈斯塔在场：所在地点+1线索"
                else:
                    ctx.extra["token_text"] = f"石板 -{v}"
            elif token == ChaosTokenType.ELDER_THING:
                v = 5 if hard else 3
                ctx.modify_amount(-v, "dc_elder_thing")
                if ctx.skill_type is not None and ctx.skill_type.value in ("combat", "agility"):
                    engaged = [iid for iid in inv.threat_area]
                    is_monster_fight = any(
                        (lambda cd: cd is not None and any(k in (cd.keywords or []) for k in ("monster", "ancient_one")))(
                            self.game_state.get_card_data(self.game_state.get_card_instance(iid).card_id))
                        for iid in engaged
                        if self.game_state.get_card_instance(iid) is not None
                    )
                    if is_monster_fight:
                        pending.add("dc_elder_lose_action")
                        ctx.extra["token_text"] = f"旧神之物 -{v}（对抗怪物/古神：失去1行动）"
                    else:
                        ctx.extra["token_text"] = f"旧神之物 -{v}"
                else:
                    ctx.extra["token_text"] = f"旧神之物 -{v}"

    def _random_discard_from_hand(self, inv) -> None:
        if inv.hand:
            import random as _rnd
            dropped = _rnd.choice(inv.hand)
            inv.hand.remove(dropped)
            inv.discard.append(dropped)

    def _set_aside_monster_under_scenario(self) -> bool:
        """把 1 个搁置的怪物敌人移到剧本牌堆下（简化：记录于 vars）。"""
        monsters = self.s.vars.get("set_aside_monsters") or []
        if not monsters:
            return False
        card_id = monsters.pop(0)
        self.s.vars.setdefault("under_scenario_deck", []).append(card_id)
        return True

    def _ready_ghoul_or_specter_at(self, location_id: str, ready: bool = False) -> object | None:
        loc = self.game_state.get_location(location_id)
        if loc is None:
            return None
        for iid in loc.enemies:
            inst = self.game_state.get_card_instance(iid)
            cd = self.game_state.get_card_data(inst.card_id) if inst else None
            if cd is None:
                continue
            kws = cd.keywords or []
            if "ghoul" not in kws and "specter" not in kws:
                continue
            if ready:
                inst.exhausted = False
                return inst
            if not inst.exhausted:
                return inst
        return None

    def _doomed_enemy_near(self, inv) -> bool:
        ids = list(inv.threat_area)
        loc = self.game_state.get_location(inv.location_id)
        if loc:
            ids += list(loc.enemies)
        for iid in ids:
            inst = self.game_state.get_card_instance(iid)
            if inst is not None and (getattr(inst, "doom", 0) or 0) >= 1:
                return True
        return False

    def _scenario_token_fail_effects(self, ctx) -> None:
        """Conditional effects when the test fails."""
        pending = self._token_pending.get(ctx.investigator_id)
        if not pending:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if "gathering_cultist_horror" in pending:
            inv.horror += 1
            pending.discard("gathering_cultist_horror")
        if "gathering_cultist_horror2" in pending:
            inv.horror += 2
            pending.discard("gathering_cultist_horror2")
        if "gathering_skull_hard_ghoul" in pending:
            pulled = self._pull_enemy_by_keyword("ghoul")
            if pulled:
                cd = self.game_state.get_card_data(pulled)
                ctx.game_state.log_effect(f"💀 骷髅失败效果：抽到食屍鬼敌人《{cd.name_cn if cd else pulled}》")
                self._spawn_enemy_from_encounter(pulled, ctx.investigator_id)
            pending.discard("gathering_skull_hard_ghoul")
        if "midnight_tablet_clue" in pending:
            if inv.clues > 0:
                inv.clues -= 1
                loc = ctx.game_state.get_location(inv.location_id)
                if loc is not None:
                    loc.clues += 1
            pending.discard("midnight_tablet_clue")
        if "midnight_tablet_clues_all" in pending:
            if inv.clues > 0:
                loc = ctx.game_state.get_location(inv.location_id)
                if loc is not None:
                    loc.clues += inv.clues
                    inv.clues = 0
            pending.discard("midnight_tablet_clues_all")
        if "devourer_skull_hard_monster" in pending:
            pulled = self._pull_enemy_by_keyword("monster")
            if pulled:
                cd = self.game_state.get_card_data(pulled)
                ctx.game_state.log_effect(f"💀 骷髅失败效果：抽到怪物敌人《{cd.name_cn if cd else pulled}》")
                self._spawn_enemy_from_encounter(pulled, ctx.investigator_id)
            pending.discard("devourer_skull_hard_monster")

        # --- Dunwich ---
        if "eca_skull_deck3" in pending:
            self._discard_top_of_deck(inv, 3)
            ctx.game_state.log_effect("💀 骷髅失败效果：弃牌堆顶3张")
            pending.discard("eca_skull_deck3")
        if "eca_skull_deck5" in pending:
            self._discard_top_of_deck(inv, 5)
            ctx.game_state.log_effect("💀 骷髅失败效果：弃牌堆顶5张")
            pending.discard("eca_skull_deck5")
        if "thaw_tablet_lose3" in pending:
            inv.resources = max(0, inv.resources - 3)
            ctx.game_state.log_effect("💀 石板失败效果：失去3资源")
            pending.discard("thaw_tablet_lose3")
        if "thaw_cultist_hard_lose3" in pending:
            inv.resources = max(0, inv.resources - 3)
            ctx.game_state.log_effect("💀 异教徒失败效果：失去3资源")
            pending.discard("thaw_cultist_hard_lose3")
        if "tmm_cultist_spawn_horror" in pending:
            if not self._enemy_card_in_play("hunting_horror"):
                self._spawn_enemy_from_encounter("hunting_horror", ctx.investigator_id)
                ctx.game_state.log_effect("💀 异教徒失败效果：追獵恐魔生成")
            pending.discard("tmm_cultist_spawn_horror")
        if "tmm_tablet_return_clue" in pending:
            if inv.clues > 0:
                inv.clues -= 1
                loc = ctx.game_state.get_location(inv.location_id)
                if loc is not None:
                    loc.clues += 1
            ctx.game_state.log_effect("💀 石板效果：1个线索放回所在地点")
            pending.discard("tmm_tablet_return_clue")
        if "tmm_elder_discard_asset" in pending:
            # 简化：弃置费用最低的支援（官方为玩家自选）
            cheapest = None
            cheapest_cost = 999
            for iid in inv.play_area:
                inst = self.game_state.get_card_instance(iid)
                cd = self.game_state.get_card_data(inst.card_id) if inst else None
                if cd is not None and (cd.cost or 0) < cheapest_cost:
                    cheapest, cheapest_cost = iid, (cd.cost or 0)
            if cheapest is not None:
                inst = self.game_state.get_card_instance(cheapest)
                cd = self.game_state.get_card_data(inst.card_id)
                inv.play_area.remove(cheapest)
                inv.discard.append(inst.card_id)
                mgr = getattr(self.game, "slot_managers", {}).get(ctx.investigator_id)
                if mgr:
                    mgr.vacate(cheapest)
                self.game_state.cards_in_play.pop(cheapest, None)
                ctx.game_state.log_effect(f"💀 旧神之物失败效果：弃置支援《{cd.name_cn if cd else inst.card_id}》（自动选最低费）")
            pending.discard("tmm_elder_discard_asset")
        if "ece_cultist_lose_actions" in pending:
            if inv.actions_remaining > 0:
                inv.actions_remaining = 0
                ctx.game_state.log_effect("💀 异教徒失败效果：失去所有剩余行动")
            pending.discard("ece_cultist_lose_actions")
        if "ece_elder_discard_hand" in pending:
            if inv.hand:
                import random as _rnd
                dropped = _rnd.choice(inv.hand)
                inv.hand.remove(dropped)
                inv.discard.append(dropped)
                cd = self.game_state.get_card_data(dropped)
                ctx.game_state.log_effect(f"💀 旧神之物失败效果：随机弃1手牌《{cd.name_cn if cd else dropped}》（官方为自选）")
            pending.discard("ece_elder_discard_hand")
        if "ece_elder_discard_hand_margin" in pending:
            # 每低于难度1点弃1张手牌（简化：随机弃，官方为自选）
            import random as _rnd
            margin = max(0, (ctx.difficulty or 0) - (ctx.modified_skill or 0))
            dropped_names = []
            for _ in range(min(margin, len(inv.hand))):
                dropped = _rnd.choice(inv.hand)
                inv.hand.remove(dropped)
                inv.discard.append(dropped)
                cd = self.game_state.get_card_data(dropped)
                dropped_names.append(cd.name_cn if cd else dropped)
            if dropped_names:
                ctx.game_state.log_effect(f"💀 旧神之物失败效果：弃{margin}张手牌（{'、'.join(dropped_names)}）")
            pending.discard("ece_elder_discard_hand_margin")
        if "bota_cultist_clue_to_loc" in pending:
            loc = ctx.game_state.get_location(inv.location_id)
            if loc is not None:
                loc.clues += 1
            ctx.game_state.log_effect("💀 异教徒失败效果：供应堆放1线索到所在地点")
            pending.discard("bota_cultist_clue_to_loc")
        if "bota_elder_doom_agenda" in pending:
            ctx.game_state.scenario.doom_on_agenda += 1
            ctx.game_state.log_effect("💀 旧神之物失败效果：当前密谋+1毁灭")
            self._check_agenda_threshold()
            pending.discard("bota_elder_doom_agenda")
        if "uau_cultist_horror" in pending:
            inv.horror += 1
            ctx.game_state.log_effect("💀 异教徒失败效果：受1恐惧")
            pending.discard("uau_cultist_horror")
        if "uau_cultist_hard_dh" in pending:
            inv.damage += 1
            inv.horror += 1
            ctx.game_state.log_effect("💀 异教徒失败效果：受1伤害1恐惧")
            pending.discard("uau_cultist_hard_dh")
        if "uau_elder_brood_attack" in pending:
            source = getattr(ctx, "source", None)
            inst = self.game_state.get_card_instance(source) if source else None
            if inst is not None and inst.card_id == "brood_of_yog_sothoth":
                cd = self.game_state.get_card_data(inst.card_id)
                if cd is not None:
                    inv.damage += cd.enemy_damage or 0
                    inv.horror += cd.enemy_horror or 0
                    ctx.game_state.log_effect("💀 旧神之物效果：猶格·索托斯之子立刻攻击你")
            pending.discard("uau_elder_brood_attack")
        if "lits_tablet_yog_attack" in pending:
            if self._enemy_card_in_play("yog_sothoth"):
                cd = self.game_state.get_card_data("yog_sothoth")
                if cd is not None:
                    inv.damage += cd.enemy_damage or 0
                    inv.horror += cd.enemy_horror or 0
                    ctx.game_state.log_effect("💀 石板效果：猶格·索托斯立刻攻击你")
            pending.discard("lits_tablet_yog_attack")

        # --- Carcosa ---
        if "tlk_skull_possessed_doom" in pending:
            possessed = self._enemies_with_keyword_in_play("possessed")
            if possessed:
                target_iid = possessed[0]
                if self._is_hard_difficulty:
                    # 困难面：剩余生命值最多的附身敌人
                    best = -1
                    for iid in possessed:
                        inst = self.game_state.get_card_instance(iid)
                        cd = self.game_state.get_card_data(inst.card_id) if inst else None
                        remain = (cd.enemy_health or 0) - (inst.damage or 0) if inst and cd else 0
                        if remain > best:
                            best, target_iid = remain, iid
                inst = self.game_state.get_card_instance(target_iid)
                if inst is not None:
                    inst.doom += 1
                    ctx.game_state.log_effect("💀 骷髅失败效果：附身敌人+1毁灭")
            pending.discard("tlk_skull_possessed_doom")
        if "tlk_cultist_clue" in pending:
            if inv.clues > 0:
                inv.clues -= 1
                loc = ctx.game_state.get_location(inv.location_id)
                if loc is not None:
                    loc.clues += 1
            pending.discard("tlk_cultist_clue")
        if "tlk_tablet_horror" in pending:
            inv.horror += 1
            pending.discard("tlk_tablet_horror")
        if "tlk_elder_damage" in pending:
            inv.damage += 1
            pending.discard("tlk_elder_damage")
        if "eotp_cultist_doom" in pending:
            target = self._nearest_enemy_with(inv, None)
            if target:
                inst = self.game_state.get_card_instance(target)
                if inst is not None:
                    inst.doom += 1
                    ctx.game_state.log_effect("💀 异教徒失败效果：最近敌人+1毁灭")
            pending.discard("eotp_cultist_doom")
        if "eotp_tablet_discard" in pending:
            self._random_discard_from_hand(inv)
            ctx.game_state.log_effect("💀 石板失败效果：随机弃1手牌")
            pending.discard("eotp_tablet_discard")
        if "eotp_elder_horror" in pending:
            inv.horror += 1
            pending.discard("eotp_elder_horror")
        if "tuo_skull_monster_under" in pending:
            if self._set_aside_monster_under_scenario():
                ctx.game_state.log_effect("💀 骷髅失败效果：搁置怪物置于剧本牌堆下")
            pending.discard("tuo_skull_monster_under")
        if "tuo_symbol_horror" in pending:
            inv.horror += 1
            pending.discard("tuo_symbol_horror")
        if "apot_cultist_byakhee" in pending:
            self._byakhee_move_step()
            ctx.game_state.log_effect("💀 异教徒失败效果：拜亚基移动")
            pending.discard("apot_cultist_byakhee")
        if "apot_elder_resources" in pending:
            margin = max(0, (ctx.difficulty or 0) - (ctx.modified_skill or 0))
            if margin:
                inv.resources = max(0, inv.resources - margin)
                ctx.game_state.log_effect(f"💀 旧神之物失败效果：失去{margin}资源")
            pending.discard("apot_elder_resources")
        if "tpm_elder_pull_ghoul" in pending:
            pulled = self._pull_enemy_by_keyword("ghoul") or self._pull_enemy_by_keyword("specter")
            if pulled:
                cd = self.game_state.get_card_data(pulled)
                ctx.game_state.log_effect(f"💀 旧神之物失败效果：抽到敌人《{cd.name_cn if cd else pulled}》")
                self._spawn_enemy_from_encounter(pulled, ctx.investigator_id)
            pending.discard("tpm_elder_pull_ghoul")
        if "bsr_tablet_doom" in pending:
            ctx.game_state.scenario.doom_on_agenda += 1
            self._check_agenda_threshold()
            ctx.game_state.log_effect("💀 石板失败效果：当前密谋+1毁灭")
            pending.discard("bsr_tablet_doom")
        if "bsr_elder_pull_byakhee" in pending:
            pulled = self._pull_enemy_by_keyword("byakhee")
            if pulled:
                cd = self.game_state.get_card_data(pulled)
                ctx.game_state.log_effect(f"💀 旧神之物失败效果：抽到拜亚基《{cd.name_cn if cd else pulled}》")
                self._spawn_enemy_from_encounter(pulled, ctx.investigator_id)
            pending.discard("bsr_elder_pull_byakhee")
        if "dc_cultist_horror1" in pending:
            inv.horror += 1
            pending.discard("dc_cultist_horror1")
        if "dc_cultist_horror2" in pending:
            inv.horror += 2
            pending.discard("dc_cultist_horror2")
        if "dc_tablet_clue" in pending:
            loc = ctx.game_state.get_location(inv.location_id)
            if loc is not None:
                loc.clues += 1
                ctx.game_state.log_effect("💀 石板失败效果：所在地点+1线索")
            pending.discard("dc_tablet_clue")
        if "dc_elder_lose_action" in pending:
            if inv.actions_remaining > 0:
                inv.actions_remaining -= 1
                ctx.game_state.log_effect("💀 旧神之物效果：失去1行动")
            pending.discard("dc_elder_lose_action")

        # 循环 3-7 失败结算
        cyc = _cycle_for_scenario(self.s.scenario_id)
        mod_name = _CYCLE_TOKEN_MODULES.get(cyc)
        if mod_name and pending:
            import importlib
            mod = importlib.import_module(f"backend.scenarios.{mod_name}")
            mod.on_fail(self, ctx, pending)
        if "lits_cultist_move_location" in pending:
            # 简化：找遭遇牌堆顶第一张地点卡放场并移动（找不到则跳过）
            scen = ctx.game_state.scenario
            moved_to = None
            for i, enc_id in enumerate(list(scen.encounter_deck)):
                cd = self.game_state.get_card_data(enc_id)
                if cd is not None and cd.type.value == "location":
                    scen.encounter_deck.pop(i)
                    if enc_id not in ctx.game_state.locations:
                        ctx.game_state.add_location(enc_id, cd, clues=cd.clue_value or 0)
                    inv.location_id = enc_id
                    moved_to = cd.name_cn or cd.name
                    break
            if moved_to:
                ctx.game_state.log_effect(f"💀 异教徒失败效果：放置并移动到【{moved_to}】")
            pending.discard("lits_cultist_move_location")

    def _scenario_token_success_effects(self, ctx) -> None:
        """Conditional effects when the test succeeds (e.g. THAW cultist)."""
        pending = self._token_success_pending.get(ctx.investigator_id)
        if not pending:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if "thaw_cultist_gain3" in pending:
            inv.resources += 3
            ctx.game_state.log_effect("🎲 异教徒成功效果：获得3资源")
            pending.discard("thaw_cultist_gain3")
        # --- Carcosa: The Pallid Mask cultist（攻击成功减伤/无伤） ---
        if "tpm_cultist_less_damage" in pending:
            ctx.extra["bonus_damage"] = int(ctx.extra.get("bonus_damage", 0) or 0) - 1
            ctx.game_state.log_effect("🎲 异教徒效果：本次攻击伤害-1")
            pending.discard("tpm_cultist_less_damage")
        if "tpm_cultist_no_damage_hard" in pending:
            # 战斗结算处钳制为 0（bonus_damage 大额负值）
            ctx.extra["bonus_damage"] = -999
            ctx.game_state.log_effect("🎲 异教徒效果：本次攻击不造成伤害")
            pending.discard("tpm_cultist_no_damage_hard")

        # 循环 3-7 成功结算
        cyc = _cycle_for_scenario(self.s.scenario_id)
        mod_name = _CYCLE_TOKEN_MODULES.get(cyc)
        if mod_name and pending:
            import importlib
            mod = importlib.import_module(f"backend.scenarios.{mod_name}")
            mod.on_success(self, ctx, pending)

    def _clear_token_pending(self, ctx) -> None:
        self._token_pending.pop(ctx.investigator_id, None)
        self._token_success_pending.pop(ctx.investigator_id, None)

    # ---------------------
    # Encounter resolution
    # ---------------------
    def resolve_encounter_card(self, card_id: str, *, investigator_id: str = "player", choice: str | None = None) -> dict[str, Any]:
        """Resolve one encounter card. Returns {"pending": bool, "message": str}.

        If a choice is required and not provided, it sets `scenario.vars['pending_choice']`.
        """
        from backend.models.enums import Skill

        inv = self.game.state.get_investigator(investigator_id)
        if inv is None:
            return {"pending": False, "message": ""}

        # Store last encounter for UI (only if the session layer hasn't
        # already stored the full card dict — don't clobber it with a bare id)
        self.s.vars.setdefault("last_encounter", card_id)

        # --- Treacheries (all used by core scenarios) ---
        if card_id == "ancient_evils":
            self.game.state.scenario.doom_on_agenda += 1
            self.log("💀 遭遇：远古邪恶（+1毁灭）")
            self._check_agenda_threshold()
            return {"pending": False, "message": "ancient_evils"}

        if card_id == "rotting_remains":
            self.log("😱 遭遇：腐烂的遗骸（意志检定3，失败按差额受恐惧）")
            self._run_skill_test(
                investigator_id,
                skill=Skill.WILLPOWER,
                difficulty=3,
                on_failure=lambda r: self.game.damage_engine.deal_damage(investigator_id, horror=_margin_fail(r)),
            )
            return {"pending": False, "message": "rotting_remains"}

        if card_id == "grasping_hands":
            self.log("🩸 遭遇：攫取之手（敏捷检定3，失败按差额受伤害）")
            self._run_skill_test(
                investigator_id,
                skill=Skill.AGILITY,
                difficulty=3,
                on_failure=lambda r: self.game.damage_engine.deal_damage(investigator_id, damage=_margin_fail(r)),
            )
            return {"pending": False, "message": "grasping_hands"}

        if card_id == "crypt_chill":
            self.log("❄️ 遭遇：墓穴寒意（意志检定4，失败弃1支援，否则受2伤害）")

            def on_failure(r):
                # Choose and discard 1 asset you control; if none, take 2 damage
                if inv.play_area:
                    iid = inv.play_area[0]
                    ci = self.game.state.get_card_instance(iid)
                    if ci:
                        self.game.damage_engine._remove_card_from_play(iid)
                        self.log("🗑️ 墓穴寒意：弃掉1张支援")
                        return
                self.game.damage_engine.deal_damage(investigator_id, damage=2)
                self.log("🩸 墓穴寒意：没有支援可弃，受到2伤害")

            self._run_skill_test(investigator_id, skill=Skill.WILLPOWER, difficulty=4, on_failure=on_failure)
            return {"pending": False, "message": "crypt_chill"}

        if card_id == "obscuring_fog":
            loc_id = inv.location_id
            self.attach_card_to_location("obscuring_fog", loc_id)
            self.log("🌫️ 遭遇：迷雾（所在地点+2隐蔽，调查成功后弃掉）")
            return {"pending": False, "message": "obscuring_fog"}

        if card_id == "dissonant_voices":
            self.add_treachery("dissonant_voices", investigator_id=investigator_id)
            self.log("🔇 遭遇：不和谐的低语（本轮不能打出支援/事件）")
            return {"pending": False, "message": "dissonant_voices"}

        if card_id == "frozen_in_fear":
            self.add_treachery("frozen_in_fear", investigator_id=investigator_id)
            self.s.vars.setdefault("frozen_in_fear_used", False)
            self.log("🥶 遭遇：恐惧冻结（本轮首次移动/战斗/闪避额外+1行动；回合结束意志3可弃）")
            return {"pending": False, "message": "frozen_in_fear"}

        if card_id == "hunting_shadow":
            # Choice: spend 1 clue OR take 2 damage
            if choice is None:
                self.s.vars["pending_choice"] = {
                    "card_id": card_id,
                    "investigator_id": investigator_id,
                    "prompt": "猎影：选择 花费1线索 或 受到2伤害",
                    "options": [
                        {"id": "spend_clue", "label": "花费1线索"},
                        {"id": "take_damage", "label": "受到2伤害"},
                    ],
                }
                return {"pending": True, "message": "pending_choice"}
            if choice == "spend_clue" and inv.clues > 0:
                inv.clues -= 1
                self.log("🧩 猎影：花费1线索")
            else:
                self.game.damage_engine.deal_damage(investigator_id, damage=2)
                self.log("🩸 猎影：受到2伤害")
            return {"pending": False, "message": "hunting_shadow"}

        if card_id == "false_lead":
            if inv.clues <= 0:
                # Surge
                self.log("🪤 虚假线索：无任何线索，获得涌现（再抽1张遭遇）")
                return {"pending": False, "message": "surge", "surge": True}

            self.log("🪤 虚假线索：智力检定4，失败按差额丢线索到地点")

            def on_failure(r):
                m = _margin_fail(r)
                loc = self.game.state.get_location(inv.location_id)
                if loc is None or m <= 0:
                    return
                moved = min(m, inv.clues)
                inv.clues -= moved
                loc.clues += moved
                self.log(f"🧩 虚假线索：放置{moved}线索到地点")

            self._run_skill_test(investigator_id, skill=Skill.INTELLECT, difficulty=4, on_failure=on_failure)
            return {"pending": False, "message": "false_lead"}

        if card_id == "locked_door":
            # Attach to location with most clues and without Locked Door attached.
            most = None
            best = -1
            for loc_id, loc in self.game.state.locations.items():
                if self.location_attachment_instance(loc_id, "locked_door"):
                    continue
                if loc.clues > best:
                    best = loc.clues
                    most = loc_id
            if most is None:
                most = inv.location_id
            self.attach_card_to_location("locked_door", most)
            self.log("🚪 遭遇：上锁的门（该地点无法调查，行动：战斗/敏捷3可弃）")
            return {"pending": False, "message": "locked_door"}

        if card_id == "mysterious_chanting":
            self.log("🕯️ 遭遇：神秘吟唱（最近邪教徒+2毁灭；若无则搜1邪教徒并抽到）")
            cultist_iid = self._find_nearest_cultist(inv.location_id)
            if cultist_iid:
                ci = self.game.state.get_card_instance(cultist_iid)
                if ci:
                    ci.doom += 2
                    self.log("💀 神秘吟唱：邪教徒+2毁灭")
                return {"pending": False, "message": "mysterious_chanting"}

            # No cultist in play: search deck+discard for a cultist enemy and draw it
            pulled = self._pull_cultist_from_encounter()
            if pulled:
                self.log("🕯️ 神秘吟唱：抽到1名邪教徒")
                self._spawn_enemy_from_encounter(pulled, investigator_id)
            return {"pending": False, "message": "mysterious_chanting"}

        if card_id == "on_wings_of_darkness":
            self.log("🦇 遭遇：黑暗之翼（敏捷4；失败受1伤1恐，并移至中央地点）")

            def on_failure(r):
                self.game.damage_engine.deal_damage(investigator_id, damage=1, horror=1)
                # Disengage non-nightgaunt enemies
                loc = self.game.state.get_location(inv.location_id)
                for enemy_iid in list(inv.threat_area):
                    enemy = self.game.state.get_card_instance(enemy_iid)
                    if enemy is None:
                        continue
                    if _is_nightgaunt(enemy.card_id):
                        continue
                    inv.threat_area.remove(enemy_iid)
                    if loc and enemy_iid not in loc.enemies:
                        loc.enemies.append(enemy_iid)
                # Move to central location
                central = self.s.vars.get("central_location")
                if central and central in self.game.state.locations:
                    inv.location_id = central
                self.log("🦇 黑暗之翼：你被拖入中央地点")

            self._run_skill_test(investigator_id, skill=Skill.AGILITY, difficulty=4, on_failure=on_failure)
            return {"pending": False, "message": "on_wings_of_darkness"}

        if card_id == "dreams_of_r_lyeh":
            self.add_treachery("dreams_of_r_lyeh", investigator_id=investigator_id)
            self.log("💤 遭遇：拉莱耶之梦（-1意志；行动：意志3可弃）")
            return {"pending": False, "message": "dreams_of_r_lyeh"}

        if card_id == "offer_of_power":
            if choice is None:
                self.s.vars["pending_choice"] = {
                    "card_id": card_id,
                    "investigator_id": investigator_id,
                    "prompt": "力量的诱惑：选择 抽2牌并在密谋上放2毁灭，或 受2恐惧",
                    "options": [
                        {"id": "draw_and_doom", "label": "抽2牌 + 密谋+2毁灭"},
                        {"id": "take_horror", "label": "受到2恐惧"},
                    ],
                }
                return {"pending": True, "message": "pending_choice"}
            if choice == "draw_and_doom":
                drew = _draw_cards(self.game, investigator_id, 2)
                self.game.state.scenario.doom_on_agenda += 2
                self.log(f"📚 力量的诱惑：抽{drew}张牌，密谋+2毁灭")
                self._check_agenda_threshold()
            else:
                self.game.damage_engine.deal_damage(investigator_id, horror=2)
                self.log("😱 力量的诱惑：受到2恐惧")
            return {"pending": False, "message": "offer_of_power"}

        if card_id == "the_yellow_sign":
            self.log("🟡 遭遇：黄衣印记（意志4；失败受2恐惧并抓取1疯狂弱点）")

            def on_failure(r):
                self.game.damage_engine.deal_damage(investigator_id, horror=2)
                # Weakness fetch (best effort)
                for cid in list(inv.deck):
                    if "madness" in cid:
                        inv.deck.remove(cid)
                        inv.hand.append(cid)
                        break

            self._run_skill_test(investigator_id, skill=Skill.WILLPOWER, difficulty=4, on_failure=on_failure)
            return {"pending": False, "message": "the_yellow_sign"}

        if card_id == "um_rdhoth_s_wrath":
            self.log("👁️ 遭遇：乌默尔多斯之怒（意志5；失败按差额：弃1牌 或 受1伤1恐）")

            def on_failure(r):
                m = _margin_fail(r)
                # default: discard from hand if possible, else take dmg/horror
                for _ in range(m):
                    if inv.hand:
                        inv.discard.append(inv.hand.pop(0))
                    else:
                        self.game.damage_engine.deal_damage(investigator_id, damage=1, horror=1)

            self._run_skill_test(investigator_id, skill=Skill.WILLPOWER, difficulty=5, on_failure=on_failure)
            return {"pending": False, "message": "um_rdhoth_s_wrath"}

        # Enemy: spawn into play (best-effort from printed Spawn text)
        cd = self.game.state.get_card_data(card_id)
        if cd is not None and cd.type.name.lower() == "enemy":
            self.log(f"👾 遭遇：生成敌人 {cd.name_cn or cd.name}")
            self._spawn_enemy_from_encounter(card_id, investigator_id)
            return {"pending": False, "message": "enemy"}

        # Path to Carcosa treacheries
        from backend.scenarios.carcosa_encounters import resolve_carcosa_treachery
        result = resolve_carcosa_treachery(self, card_id, investigator_id=investigator_id,
                                           choice=choice)
        if result is not None:
            return result

        # Dunwich Legacy treacheries
        from backend.scenarios.dunwich_encounters import resolve_dunwich_treachery
        result = resolve_dunwich_treachery(self, card_id, investigator_id=investigator_id)
        if result is not None:
            return result

        # 循环 3-7 遭遇卡（各自循环的 encounters 模块）
        cyc = _cycle_for_scenario(self.s.scenario_id)
        enc_mod = _CYCLE_ENCOUNTER_MODULES.get(cyc)
        if enc_mod:
            import importlib
            mod = importlib.import_module(f"backend.scenarios.{enc_mod}")
            result = mod.resolve_treachery(self, card_id, investigator_id=investigator_id, choice=choice)
            if result is not None:
                return result

        # Unknown/unsupported encounter card (location/etc) is ignored for now
        self.log(f"(未实现) 遭遇牌：{card_id}")
        return {"pending": False, "message": "unhandled"}

    def _run_skill_test(self, investigator_id: str, *, skill, difficulty: int, on_failure=None) -> None:
        def _ok(_r):
            return

        def _fail(r):
            if on_failure:
                on_failure(r)

        if self.skill_test_request_handler is not None:
            self.skill_test_request_handler(
                investigator_id=investigator_id,
                skill=skill,
                difficulty=difficulty,
                on_success=_ok,
                on_failure=_fail,
            )
            return

        self.game.skill_test_engine.run_test(
            investigator_id=investigator_id,
            skill_type=skill,
            difficulty=difficulty,
            committed_card_ids=[],
            on_success=_ok,
            on_failure=_fail,
        )

    def _check_agenda_threshold(self) -> None:
        from backend.engine.phase_mythos import MythosPhase

        MythosPhase(self.game.state, self.game.event_bus)._check_doom_threshold()

    def _find_nearest_cultist(self, from_location_id: str) -> str | None:
        # Prefer engaged cultists (any investigator), then same-location, then any.
        for inv in self.game_state.investigators.values():
            for iid in inv.threat_area:
                ci = self.game.state.get_card_instance(iid)
                if ci and _is_cultist_enemy_id(ci.card_id):
                    return iid
        loc = self.game.state.get_location(from_location_id)
        if loc:
            for iid in loc.enemies:
                ci = self.game.state.get_card_instance(iid)
                if ci and _is_cultist_enemy_id(ci.card_id):
                    return iid
        for iid, ci in self.game.state.cards_in_play.items():
            if _is_cultist_enemy_id(ci.card_id):
                return iid
        return None

    def _pull_cultist_from_encounter(self) -> str | None:
        s = self.game.state.scenario
        # Search encounter deck then discard
        for pile_name in ("encounter_deck", "encounter_discard"):
            pile = getattr(s, pile_name)
            for card_id in list(pile):
                if _is_cultist_enemy_id(card_id):
                    pile.remove(card_id)
                    return card_id
        return None

    def _pull_enemy_by_keyword(self, keyword: str) -> str | None:
        """Search encounter deck then discard for an enemy with the keyword."""
        s = self.game.state.scenario
        for pile_name in ("encounter_deck", "encounter_discard"):
            pile = getattr(s, pile_name)
            for card_id in list(pile):
                cd = self.game_state.get_card_data(card_id)
                if cd is not None and cd.type.value == "enemy" \
                        and keyword in (getattr(cd, "keywords", None) or []):
                    pile.remove(card_id)
                    return card_id
        return None

    def _spawn_enemy_from_encounter(self, card_id: str, investigator_id: str) -> None:
        from backend.models.state import CardInstance

        inv = self.game.state.get_investigator(investigator_id)
        if inv is None:
            return

        instance_id = self.game.state.next_instance_id()
        ci = CardInstance(
            instance_id=instance_id,
            card_id=card_id,
            owner_id="scenario",
            controller_id="scenario",
        )
        self.game.state.cards_in_play[instance_id] = ci

        # Spawn location from encounter text (best-effort)
        cd = self.game.state.get_card_data(card_id)
        spawn_name = _parse_spawn_location_from_text(cd.text if cd else "")
        loc_id = _find_location_by_name(self.game, spawn_name) if spawn_name else None
        if loc_id is None:
            loc_id = inv.location_id

        svars = self.game.state.scenario.vars
        is_elite = bool(cd and is_elite_enemy(cd))

        # Barricade blocks enemy *movement* into the location (handled in
        # phase_enemy hunter movement); spawning is not movement, so the
        # official card does not prevent spawns here.

        # Disc of Itzamna: reaction — cancel non-elite spawn at your location
        if not is_elite and loc_id == inv.location_id:
            for disc_iid in list(inv.play_area):
                disc = self.game.state.get_card_instance(disc_iid)
                if disc is not None and disc.card_id == "disc_of_itzamna_lv2":
                    inv.play_area.remove(disc_iid)
                    self.game.state.cards_in_play.pop(disc_iid, None)
                    inv.discard.append("disc_of_itzamna_lv2")
                    self.game.state.cards_in_play.pop(instance_id, None)
                    self.game.state.scenario.encounter_discard.append(card_id)
                    self.log("💿 伊察姆纳圆盘：取消敌人生成")
                    return

        if loc_id == inv.location_id:
            # Spawn at investigator location -> engage
            inv.threat_area.append(instance_id)
            return

        loc = self.game.state.get_location(loc_id)
        if loc:
            loc.enemies.append(instance_id)

    # ---------------------
    # Act / resolution
    # ---------------------
    def act_clue_threshold(self, act) -> int | None:
        """Effective clue threshold: ⊘ values scale by investigator count."""
        if act is None or act.clue_threshold is None:
            return None
        if getattr(act, "clue_threshold_per_investigator", False):
            return act.clue_threshold * max(1, len(self.game.state.player_order))
        return act.clue_threshold

    def _group_clues(self) -> int:
        """全组线索合计（官方：推进幕时汇集所有存活调查员的线索）。"""
        total = 0
        for inv_id in self.game.state.player_order:
            inv = self.game.state.get_investigator(inv_id)
            if inv is not None and not inv.is_defeated:
                total += inv.clues
        return total

    def can_advance_act(self, investigator_id: str = "player") -> bool:
        act = self.game.state.scenario.current_act
        if act is None:
            return False
        threshold = self.act_clue_threshold(act)
        if threshold is None:
            return False
        return self._group_clues() >= threshold

    def advance_act(self, investigator_id: str = "player") -> bool:
        act = self.game.state.scenario.current_act
        if act is None:
            return False
        inv = self.game.state.get_investigator(investigator_id)
        if inv is None:
            return False

        # Spend clues if needed — 从全组汇集（推进者先行，其余按行动顺序扣）
        threshold = self.act_clue_threshold(act)
        if threshold:
            if self._group_clues() < threshold:
                return False
            remaining = threshold
            order = [investigator_id] + [
                iid for iid in self.game.state.player_order if iid != investigator_id
            ]
            for iid in order:
                other = self.game.state.get_investigator(iid)
                if other is None:
                    continue
                take = min(other.clues, remaining)
                other.clues -= take
                remaining -= take
                if remaining <= 0:
                    break

        self.game.state.scenario.current_act_index += 1

        # Scenario-specific act effects (minimal but playable)
        if self.game.state.scenario.scenario_id == "the_gathering":
            # On advancing Act 1 -> spawn Ghoul Priest in Hallway
            if act.id == "trapped":
                self.log("📜 事件推进：你冲出书房，危险逼近（生成食尸鬼祭司）")
                self._spawn_enemy_from_encounter("ghoul_priest", investigator_id)

        return True

    def resign(self) -> str:
        """Resolve a voluntary resign (Midnight Masks). Returns resolution id."""
        s = self.game.state.scenario
        if s.scenario_id != "the_midnight_masks":
            self.set_resolution("R0", message="撤退（未定义结局）")
            return "R0"

        defeated = int(s.vars.get("cultists_defeated", 0) or 0)
        if defeated >= 6:
            res = "R1"
        elif defeated >= 3:
            res = "R2"
        else:
            res = "R3"
        self.set_resolution(res, message=f"撤退：已击败邪教徒 {defeated}")
        return res
