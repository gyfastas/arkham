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
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SCENARIO_DIR = PROJECT_ROOT / "data" / "scenarios"
ENCOUNTER_DB_PATH = PROJECT_ROOT / "data" / "encounter_cards" / "core_set.json"


def _load_json(path: Path) -> Any:
    import json

    return json.loads(path.read_text(encoding="utf-8"))


def load_core_encounter_db() -> dict[str, dict[str, Any]]:
    """Return encounter/scenario card records keyed by `id`."""
    payload = _load_json(ENCOUNTER_DB_PATH)
    cards: list[dict[str, Any]] = payload.get("cards", [])
    return {c["id"]: c for c in cards}


def load_scenario_definition(scenario_id: str) -> dict[str, Any]:
    path = SCENARIO_DIR / f"{scenario_id}.json"
    return _load_json(path)


def apply_scenario_to_game(game, scenario_id: str, *, seed: int = 1) -> None:
    """Populate `game.state` with scenario data (locations/act/agenda/encounter deck)."""
    from backend.models.enums import CardType
    from backend.models.scenario import ActCard, AgendaCard
    from backend.models.state import CardData

    scenario_def = load_scenario_definition(scenario_id)
    db = load_core_encounter_db()

    s = game.state.scenario
    s.scenario_id = scenario_id
    s.vars.setdefault("scenario_id", scenario_id)
    s.vars.setdefault("scenario_name", scenario_def.get("name"))
    s.vars.setdefault("resolution_id", None)
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
    for loc_id in scenario_def.get("locations", []):
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
    }

    s.act_cards = {}
    for act_id in s.act_deck:
        rec = db.get(act_id)
        if not rec or rec.get("type") != "act":
            raise ValueError(f"missing act in encounter db: {act_id}")
        s.act_cards[act_id] = ActCard(
            id=act_id,
            name=rec.get("name") or act_id,
            name_cn=rec.get("name_cn") or "",
            sequence=int((rec.get("meta") or {}).get("position") or 1),
            clue_threshold=clue_thresholds.get(act_id),
            text=rec.get("text") or "",
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
        )

    # --- Encounter deck ---
    encounter_sets: list[str] = scenario_def.get("encounter_sets", [])
    deck: list[str] = []

    # Scenario set-aside cards (official rules); keep them out of encounter deck.
    set_aside: set[str] = set()
    if scenario_id == "the_gathering":
        set_aside.update({"ghoul_priest", "lita_chantler"})
    for rec in db.values():
        if rec.get("encounter_code") not in encounter_sets:
            continue
        t = rec.get("type")
        if t in ("enemy", "treachery", "location"):
            # Keep map locations out of encounter deck
            if t == "location" and rec.get("id") in scenario_def.get("locations", []):
                continue
            if rec.get("id") in set_aside:
                continue
            deck.append(rec["id"])

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
                    keywords=[],
                    text=rec.get("text") or "",
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


@dataclass
class ScenarioController:
    """Scenario-specific glue: encounter resolution + branching endings.

    This controller is designed to be used by a server loop that drives
    end-of-turn / mythos flow.
    """

    game: Any
    action_log: list[str] | None = None

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

    # ---------------------
    # Helpers
    # ---------------------
    @property
    def s(self):
        return self.game.state.scenario

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
        if self.get_attached("obscuring_fog") == loc_id:
            self.remove_treachery("obscuring_fog")
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

        # Store last encounter for UI
        self.s.vars["last_encounter"] = card_id

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
            self.add_treachery("obscuring_fog", investigator_id=investigator_id, attached_to=loc_id)
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
                if self.get_attached("locked_door") == loc_id:
                    continue
                if loc.clues > best:
                    best = loc.clues
                    most = loc_id
            if most is None:
                most = inv.location_id
            self.add_treachery("locked_door", investigator_id=investigator_id, attached_to=most)
            self.log("🚪 遭遇：上锁的门（该地点无法调查，行动：战斗/敏捷4可弃）")
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

        # Unknown/unsupported encounter card (location/etc) is ignored for now
        self.log(f"(未实现) 遭遇牌：{card_id}")
        return {"pending": False, "message": "unhandled"}

    def _run_skill_test(self, investigator_id: str, *, skill, difficulty: int, on_failure=None) -> None:
        def _ok(_r):
            return

        def _fail(r):
            if on_failure:
                on_failure(r)

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
        # Prefer engaged cultists, then same-location, then any.
        inv = self.game.state.get_investigator("player")
        if inv:
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
    def can_advance_act(self, investigator_id: str = "player") -> bool:
        act = self.game.state.scenario.current_act
        if act is None:
            return False
        if act.clue_threshold is None:
            return False
        inv = self.game.state.get_investigator(investigator_id)
        if inv is None:
            return False
        return inv.clues >= act.clue_threshold

    def advance_act(self, investigator_id: str = "player") -> bool:
        act = self.game.state.scenario.current_act
        if act is None:
            return False
        inv = self.game.state.get_investigator(investigator_id)
        if inv is None:
            return False

        # Spend clues if needed
        if act.clue_threshold:
            if inv.clues < act.clue_threshold:
                return False
            inv.clues -= act.clue_threshold

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
