"""Game session: wraps the engine Game for server-side multiplayer use.

Each GameSession manages one active game instance, handling action dispatch,
state serialization with information hiding, and event capture for animation.
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

from backend.engine.game import Game
from backend.models.enums import Action, CardType, GameEvent, Phase, PlayerClass, SlotType, Skill
from backend.models.state import CardData, SkillValues
from backend.scenarios.official_core import (
    apply_scenario_to_game,
    load_scenario_definition,
    ScenarioController,
)

from server.event_logger import EventLogger
from server.player import PlayerSession
from server.state_serializer import serialize_game_state

PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Investigator / deck definitions (extracted from server_core.py)
# ---------------------------------------------------------------------------

INVESTIGATORS: dict[str, dict] = {
    "roland_banks": {
        "name": "Roland Banks",
        "name_cn": "罗兰·班克斯",
        "class": PlayerClass.GUARDIAN,
        "health": 9, "sanity": 5,
        "skills": SkillValues(willpower=3, intellect=3, combat=4, agility=2),
        "ability_cn": "你在击败敌人后可发现1条线索（简化：不自动实现）。",
    },
    "daisy_walker": {
        "name": "Daisy Walker",
        "name_cn": "黛西·沃克",
        "class": PlayerClass.SEEKER,
        "health": 5, "sanity": 9,
        "skills": SkillValues(willpower=3, intellect=5, combat=2, agility=2),
        "ability_cn": "每回合+1行动（仅典籍）。",
    },
    "skids_otoole": {
        "name": "Skids O'Toole",
        "name_cn": "斯基兹·奥图尔",
        "class": PlayerClass.ROGUE,
        "health": 8, "sanity": 6,
        "skills": SkillValues(willpower=2, intellect=3, combat=3, agility=4),
        "ability_cn": "你可以花费2资源获得+1行动（简化：不自动实现）。",
    },
    "agnes_baker": {
        "name": "Agnes Baker",
        "name_cn": "艾格尼丝·贝克",
        "class": PlayerClass.MYSTIC,
        "health": 6, "sanity": 8,
        "skills": SkillValues(willpower=5, intellect=2, combat=2, agility=3),
        "ability_cn": "你受到恐惧后可对敌人造成1伤害（简化：不自动实现）。",
    },
    "wendy_adams": {
        "name": "Wendy Adams",
        "name_cn": "温蒂·亚当斯",
        "class": PlayerClass.SURVIVOR,
        "health": 7, "sanity": 7,
        "skills": SkillValues(willpower=4, intellect=3, combat=1, agility=4),
        "ability_cn": "弃1张牌重抽混沌标记（简化：不自动实现）。",
    },
}

def _load_preset_decks() -> dict[str, dict]:
    """Load preset decks from data/preset_decks/*.json files."""
    import json as _json
    presets: dict[str, dict] = {}
    preset_dir = PROJECT_ROOT / "data" / "preset_decks"
    if not preset_dir.exists():
        return presets
    for p in sorted(preset_dir.glob("*.json")):
        try:
            data = _json.loads(p.read_text(encoding="utf-8"))
            inv_id = data.get("investigator_id", p.stem)
            for i, preset in enumerate(data.get("presets", [])):
                preset_id = f"{inv_id}_preset_{i}" if i > 0 else f"{inv_id}_starter"
                presets[preset_id] = {
                    "name_cn": preset.get("name", inv_id),
                    "investigator_id": inv_id,
                    "cards": preset.get("cards", []),
                }
        except (ValueError, KeyError):
            continue
    return presets


DECK_PRESETS: dict[str, dict] = _load_preset_decks()


def _card_name_cn(g: Game, card_id: str) -> str:
    """Display name for a card (Chinese preferred)."""
    cd = g.state.get_card_data(card_id)
    if cd is None:
        return card_id
    return cd.name_cn or cd.name or card_id


def _lookup_encounter_card(card_id: str, campaign: str = "core") -> dict | None:
    """Look up encounter card data from JSON for client display."""
    from backend.scenarios.official_core import load_encounter_db_for_campaign
    db = load_encounter_db_for_campaign(campaign)
    rec = db.get(card_id)
    if not rec:
        return {"id": card_id, "name": card_id, "name_cn": "", "type": "treachery", "text": "", "traits": []}
    traits = rec.get("traits") or []
    if isinstance(traits, str):  # 敦威治库部分 traits 是字符串
        traits = [traits]
    result = {
        "id": card_id,
        "name": rec.get("name", card_id),
        "name_cn": rec.get("name_cn", ""),
        "type": rec.get("type", "treachery"),
        "text": rec.get("text", ""),
        "traits": traits,
    }
    # Enemy stats for popup display (fight/health/evade/damage/horror)
    stats = rec.get("stats") or {}
    for key in ("fight", "health", "evade", "damage", "horror"):
        if stats.get(key) is not None:
            result[key] = stats[key]
    return result


# ---------------------------------------------------------------------------
# Card loading helpers
# ---------------------------------------------------------------------------

def _load_investigator_json(inv_id: str) -> dict | None:
    """Load investigator JSON from data/investigators/."""
    import json as _json
    p = PROJECT_ROOT / "data" / "investigators" / f"{inv_id}.json"
    if p.exists():
        return _json.loads(p.read_text(encoding="utf-8"))
    return None


def get_investigator_detail(inv_id: str) -> dict | None:
    """Return full investigator detail for client display."""
    data = _load_investigator_json(inv_id)
    if data:
        return {
            "id": data["id"],
            "name": data.get("name", ""),
            "name_cn": data.get("name_cn", ""),
            "title_cn": data.get("title_cn", ""),
            "class": data.get("class", "neutral"),
            "health": data.get("health", 5),
            "sanity": data.get("sanity", 5),
            "skills": data.get("skills", {}),
            "ability_cn": data.get("ability_cn", ""),
            "deck_requirements": data.get("deck_requirements"),
            "signature_cards": data.get("signature_cards", []),
            "weakness": data.get("weakness", ""),
        }
    # Fallback to hardcoded INVESTIGATORS dict
    inv_def = INVESTIGATORS.get(inv_id)
    if not inv_def:
        return None
    skills = inv_def.get("skills")
    return {
        "id": inv_id,
        "name": inv_def.get("name", ""),
        "name_cn": inv_def.get("name_cn", ""),
        "title_cn": "",
        "class": inv_def["class"].value,
        "health": inv_def.get("health", 5),
        "sanity": inv_def.get("sanity", 5),
        "skills": {
            "willpower": skills.willpower if skills else 0,
            "intellect": skills.intellect if skills else 0,
            "combat": skills.combat if skills else 0,
            "agility": skills.agility if skills else 0,
        },
        "ability_cn": inv_def.get("ability_cn", ""),
        "deck_requirements": None,
        "signature_cards": [],
        "weakness": "",
    }


def list_available_cards(investigator_id: str = "", xp_available: int = 0) -> dict:
    """Return player cards + presets for deck building.

    Returns: {"cards": [...], "presets": [...], "deck_requirements": {...},
              "signature_cards": [...], "weakness_cards": [...]}
    """
    import json as _json

    # Load deck requirements from investigator JSON
    deck_req: dict | None = None
    allowed_classes: dict[str, tuple[int, int]] = {}  # class -> (min_level, max_level)

    inv_json = _load_investigator_json(investigator_id) if investigator_id else None
    if inv_json and inv_json.get("deck_requirements"):
        deck_req = inv_json["deck_requirements"]
        for cls, levels in deck_req.get("cards", {}).items():
            allowed_classes[cls] = (levels.get("min_level", 0), levels.get("max_level", 5))
    elif investigator_id:
        # Fallback: investigator's class + neutral
        inv_def = INVESTIGATORS.get(investigator_id)
        if inv_def:
            inv_class = inv_def["class"].value
            allowed_classes[inv_class] = (0, 5)
            allowed_classes["neutral"] = (0, 5)

    # Gather signature/weakness IDs to exclude from the buildable pool
    sig_ids: set[str] = set()
    weak_ids: set[str] = set()
    if inv_json:
        for s in inv_json.get("signature_cards", []):
            sig_ids.add(s)
        w = inv_json.get("weakness", "")
        if w:
            weak_ids.add(w)

    cards: list[dict] = []
    # Also collect full data for signature/weakness cards
    sig_card_data: list[dict] = []
    weak_card_data: list[dict] = []

    base = PROJECT_ROOT / "data" / "player_cards"
    for p in base.rglob("*.json"):
        if p.name == "schema.json":
            continue
        data = _json.loads(p.read_text(encoding="utf-8"))
        card_id = data.get("id")
        if not card_id:
            continue
        card_class = data.get("class", "neutral")
        card_type = data.get("type", "")
        card_level = data.get("level") or 0

        card_info = {
            "id": card_id,
            "name": data.get("name", card_id),
            "name_cn": data.get("name_cn", ""),
            "type": card_type,
            "class": card_class,
            "cost": data.get("cost"),
            "level": card_level,
            "text": data.get("text", ""),
            "text_cn": data.get("text_cn", ""),
            "slots": data.get("slots", []),
            "skill_icons": data.get("skill_icons", {}),
            "traits": data.get("traits", []),
            "health": data.get("health"),
            "sanity": data.get("sanity"),
            "unique": data.get("unique", False),
            "victory": data.get("victory", 0),
            "allowed": True,
        }

        # Signature/weakness cards go to separate lists, not the buildable pool
        if card_id in sig_ids:
            sig_card_data.append(card_info)
            continue
        if card_id in weak_ids:
            weak_card_data.append(card_info)
            continue

        # Only allow playable card types in the buildable pool
        if card_type not in ("asset", "event", "skill"):
            continue

        # Check deck building rules
        if allowed_classes:
            if card_class not in allowed_classes:
                continue
            min_lv, max_lv = allowed_classes[card_class]
            if not (min_lv <= card_level <= max_lv):
                continue

        # XP check: card is "allowed" if player can afford it
        # Level 0 cards are always allowed; level N costs N XP
        card_info["allowed"] = card_level == 0 or card_level <= xp_available
        cards.append(card_info)

    cards.sort(key=lambda c: (c["class"], c["level"], c["type"], c.get("cost") or 0, c["id"]))

    # Collect presets for this investigator
    presets = []
    for preset_id, preset in DECK_PRESETS.items():
        if not investigator_id or preset.get("investigator_id") == investigator_id:
            presets.append({
                "id": preset_id,
                "name": preset.get("name_cn", preset_id),
                "cards": preset.get("cards", []),
            })

    return {
        "cards": cards,
        "presets": presets,
        "deck_requirements": deck_req,
        "signature_cards": sig_card_data,
        "weakness_cards": weak_card_data,
    }


def _load_player_cards(g: Game) -> None:
    """Load ``data/player_cards/**/*.json`` into ``card_database``."""
    def to_slots(values: list[str]) -> list[SlotType]:
        out: list[SlotType] = []
        for s in values or []:
            if s.endswith("_x2"):
                base = s[:-3]
                out.extend([SlotType(base), SlotType(base)])
            elif s == "hand_x2":
                out.extend([SlotType.HAND, SlotType.HAND])
            elif s == "arcane_x2":
                out.extend([SlotType.ARCANE, SlotType.ARCANE])
            else:
                out.append(SlotType(s))
        return out

    base = PROJECT_ROOT / "data" / "player_cards"
    for p in base.rglob("*.json"):
        if p.name == "schema.json":
            continue
        data = json.loads(p.read_text(encoding="utf-8"))
        card_id = data.get("id")
        if not card_id:
            continue
        try:
            cd = CardData(
                id=card_id,
                name=data.get("name") or card_id,
                name_cn=data.get("name_cn") or "",
                type=CardType(data.get("type")),
                card_class=PlayerClass(data.get("class") or "neutral"),
                cost=data.get("cost"),
                level=int(data.get("level") or 0),
                traits=list(data.get("traits") or []),
                skill_icons=dict(data.get("skill_icons") or {}),
                slots=to_slots(list(data.get("slots") or [])),
                text=data.get("text") or "",
                text_cn=data.get("text_cn") or "",
                health=data.get("health"),
                sanity=data.get("sanity"),
                pack=data.get("pack") or "",
                unique=bool(data.get("unique") or False),
                fast=bool(data.get("fast") or False),
                victory=int(data.get("victory") or 0),
            )
        except Exception:
            continue
        g.register_card_data(cd)


# ---------------------------------------------------------------------------
# GameSession
# ---------------------------------------------------------------------------

class GameSession:
    """One running game instance, managed by a Room.

    Wraps the backend ``Game`` engine and provides:
    - Action dispatch with player validation
    - Per-player state serialization (information hiding)
    - Event capture for client animation
    """

    def __init__(self, room_id: str) -> None:
        self.room_id = room_id
        self.game: Game | None = None
        self.controller: ScenarioController | None = None
        self.event_logger: EventLogger | None = None
        self.action_log: list[str] = []
        self.game_over: dict | None = None
        self._players: dict[str, PlayerSession] = {}

    @property
    def is_started(self) -> bool:
        return self.game is not None

    def add_player(self, player: PlayerSession) -> None:
        self._players[player.player_id] = player

    def remove_player(self, player_id: str) -> None:
        self._players.pop(player_id, None)

    def setup(
        self,
        *,
        scenario_id: str = "the_gathering",
        investigator_id: str = "daisy_walker",
        deck_preset: str = "",
        deck_cards: list[str] | None = None,
        seed: int | None = None,
    ) -> dict:
        """Initialize a single-player game (multi-player setup in Phase 4)."""
        self.action_log = []
        self.game_over = None

        if seed is None:
            import random as _random
            seed = _random.SystemRandom().randrange(2**31)

        g = Game(scenario_id)
        g.chaos_bag.seed(seed)

        _load_player_cards(g)

        # Filler card
        filler = CardData(
            id="filler", name="Filler Card", name_cn="填充卡",
            type=CardType.SKILL, card_class=PlayerClass.NEUTRAL,
            cost=None, skill_icons={"wild": 1}, text="占位符。",
        )
        g.register_card_data(filler)

        # Investigator — try JSON first, then hardcoded fallback
        inv_json = _load_investigator_json(investigator_id)
        inv_def = INVESTIGATORS.get(investigator_id)
        if inv_json:
            cls_str = inv_json.get("class", "neutral")
            try:
                pc = PlayerClass(cls_str)
            except ValueError:
                pc = PlayerClass.NEUTRAL
            sk = inv_json.get("skills", {})
            inv_data = CardData(
                id=investigator_id,
                name=inv_json.get("name", investigator_id),
                name_cn=inv_json.get("name_cn", ""),
                type=CardType.INVESTIGATOR,
                card_class=pc,
                health=inv_json.get("health", 5),
                sanity=inv_json.get("sanity", 5),
                skills=SkillValues(
                    willpower=sk.get("willpower", 1),
                    intellect=sk.get("intellect", 1),
                    combat=sk.get("combat", 1),
                    agility=sk.get("agility", 1),
                ),
                ability=inv_json.get("ability_cn", ""),
            )
        elif inv_def:
            inv_data = CardData(
                id=investigator_id,
                name=inv_def["name"],
                name_cn=inv_def["name_cn"],
                type=CardType.INVESTIGATOR,
                card_class=inv_def["class"],
                health=inv_def["health"],
                sanity=inv_def["sanity"],
                skills=inv_def["skills"],
                ability=inv_def.get("ability_cn") or "",
            )
        else:
            # Ultimate fallback
            fb = INVESTIGATORS["daisy_walker"]
            inv_data = CardData(
                id="daisy_walker",
                name=fb["name"], name_cn=fb["name_cn"],
                type=CardType.INVESTIGATOR, card_class=fb["class"],
                health=fb["health"], sanity=fb["sanity"],
                skills=fb["skills"], ability=fb.get("ability_cn") or "",
            )
        g.register_card_data(inv_data)

        # Deck — build base 30 cards
        deck_ids: list[str] = []
        if deck_cards:
            # Custom deck from deck builder
            deck_ids = list(deck_cards)
        elif deck_preset and deck_preset in DECK_PRESETS:
            deck_ids = list(DECK_PRESETS[deck_preset]["cards"])
        else:
            for preset_id, preset in DECK_PRESETS.items():
                if preset.get("investigator_id") == investigator_id:
                    deck_ids = list(preset["cards"])
                    break

        deck_ids = [cid for cid in deck_ids if g.state.get_card_data(cid) is not None]
        if len(deck_ids) < 30:
            deck_ids += ["filler"] * (30 - len(deck_ids))
        elif len(deck_ids) > 30:
            deck_ids = deck_ids[:30]

        # Add signature cards and weakness (don't count toward 30-card limit)
        sig_cards: list[str] = []
        if inv_json:
            for sig_id in inv_json.get("signature_cards", []):
                if g.state.get_card_data(sig_id) is not None and sig_id not in deck_ids:
                    sig_cards.append(sig_id)
            weakness_id = inv_json.get("weakness", "")
            if weakness_id and g.state.get_card_data(weakness_id) is not None and weakness_id not in deck_ids and weakness_id not in sig_cards:
                sig_cards.append(weakness_id)

        # Official setup rule: each deck also includes 1 random basic weakness
        basic_weakness_pool = [
            "chronophobia_lv0", "hypochondria", "indebted_lv0", "internal_injury_lv0",
        ]
        basic_weakness_pool = [
            w for w in basic_weakness_pool
            if g.state.get_card_data(w) is not None and w not in deck_ids and w not in sig_cards
        ]
        if basic_weakness_pool:
            bw = random.choice(basic_weakness_pool)
            sig_cards.append(bw)
            self.action_log.append(f"🃏 随机基础弱点：{_card_name_cn(g, bw)}")
        deck_ids.extend(sig_cards)

        random.shuffle(deck_ids)


        # Scenario
        apply_scenario_to_game(g, scenario_id, seed=seed)
        scen = load_scenario_definition(scenario_id)
        g.add_investigator("player", inv_data, deck=deck_ids, starting_location=scen["start_location"])
        g.setup()
        # Official rule: opening hand mulligan (redraw any number of cards, once)
        g.state.scenario.vars["mulligan_available"] = True

        if scenario_id == "the_midnight_masks":
            g.state.scenario.vars["central_location"] = "downtown"
        else:
            g.state.scenario.vars["central_location"] = scen["start_location"]

        self.controller = ScenarioController(g, action_log=self.action_log)
        self.controller.attach()

        # Event logger for animation
        self.event_logger = EventLogger(g.event_bus)

        g.state.scenario.current_phase = Phase.INVESTIGATION
        g.state.scenario.round_number = 1

        # Initialize investigator actions for first turn
        inv = g.state.get_investigator("player")
        if inv:
            inv.actions_remaining = 3

        # 第1轮调查阶段开始事件（黛西典籍行动授予等，须在行动点重置之后）
        from backend.engine.event_bus import EventContext
        for inv_id in g.state.player_order:
            g.event_bus.emit(EventContext(
                game_state=g.state,
                event=GameEvent.INVESTIGATION_PHASE_BEGINS,
                investigator_id=inv_id,
            ))

        self.action_log.append(f"=== 核心剧本：{scen.get('name_cn', scenario_id)} ===")
        self.action_log.append(f"调查员：{inv_data.name_cn}")
        self.action_log.append("第1轮 调查阶段")

        self.game = g
        return {"success": True, "message": "游戏已初始化"}

    def _clear_game_over(self) -> None:
        if self.game is None:
            return
        res = self.game.state.scenario.vars.get("resolution_id")
        if res and not self.game_over:
            win = res in {"R1", "R2"}
            msg = self.game.state.scenario.vars.get("resolution_message") or f"结局：{res}"
            self.game_over = {"type": "win" if win else "lose", "message": msg}

    def get_state_for_player(self, player_id: str) -> dict:
        """Return serialized game state for a specific player."""
        if self.game is None:
            return {}
        self._clear_game_over()
        # For now, single-player always views as "player"
        player = self._players.get(player_id)
        viewer = "player"
        if player and player.investigator_ids:
            viewer = player.investigator_ids[0]
        return serialize_game_state(
            self.game,
            action_log=self.action_log,
            game_over=self.game_over,
            viewer_investigator_id=viewer,
        )

    def get_victory_xp(self) -> int:
        """Calculate total XP from victory display cards."""
        if self.game is None:
            return 0
        total = 0
        for card_id in self.game.state.scenario.victory_display:
            cd = self.game.state.card_database.get(card_id)
            if cd and hasattr(cd, 'victory'):
                total += cd.victory
        return total

    def handle_action(self, player_id: str, data: dict) -> dict:
        """Process a player action. Returns result dict with events."""
        if self.game is None:
            return {"success": False, "message": "游戏未初始化"}

        inv = self.game.state.get_investigator("player")
        if inv is None:
            return {"success": False, "message": "未找到调查员"}
        if self.game_over or inv.is_defeated:
            return {"success": False, "message": "游戏已结束"}

        act = data.get("action")
        if not act:
            return {"success": False, "message": "缺少 action"}

        # Clear previous encounter card display
        self.game.state.scenario.vars.pop("last_encounter", None)

        # Flush any previous events
        if self.event_logger:
            self.event_logger.flush()

        # Resolve pending choice
        if act == "RESOLVE_CHOICE":
            result = self._resolve_choice(data)
        elif act == "MULLIGAN":
            result = self._mulligan(inv, data)
        elif act == "ADVANCE_ACT":
            result = self._advance_act(inv)
        elif act == "RESIGN":
            result = self._resign()
        elif act == "LOCKED_DOOR_TEST":
            result = self._locked_door_test(inv, data)
        elif act == "ACTIVATE_ASSET":
            result = self._activate_asset(inv, data)
        elif act == "ACTIVATE_CARD":
            result = self._activate_card(inv, data)
        else:
            result = self._normal_action(inv, act, data)

        # Capture events for animation
        events = self.event_logger.flush() if self.event_logger else []
        self._drain_effect_log()
        result["events"] = events
        self._clear_game_over()
        return result

    def handle_end_turn(self, player_id: str) -> dict:
        """End the current player's turn."""
        if self.game is None:
            return {"success": False, "message": "游戏未初始化"}

        inv = self.game.state.get_investigator("player")
        if inv is None:
            return {"success": False, "message": "未找到调查员"}
        if inv.is_defeated or self.game_over:
            return {"success": False, "message": "游戏已结束"}

        if self.event_logger:
            self.event_logger.flush()

        # Frozen in Fear test at end of turn
        if self.controller and self.controller.has_treachery("frozen_in_fear"):
            ok = {"success": False}

            def on_success(_r):
                ok["success"] = True
                self.controller.remove_treachery("frozen_in_fear")
                self.action_log.append("🥶 ���惧冻结：意志检定成功，弃掉")

            self.game.skill_test_engine.run_test(
                investigator_id="player",
                skill_type=Skill.WILLPOWER,
                difficulty=3,
                committed_card_ids=[],
                on_success=on_success,
                on_failure=lambda _r: None,
            )

        # Enemy Phase
        self.action_log.append("--- 敌人阶段 ---")
        old_d, old_h = inv.damage, inv.horror
        self.game.enemy_phase.resolve()
        if inv.damage > old_d or inv.horror > old_h:
            self.action_log.append(f"👹 敌人攻击：{inv.damage - old_d}伤害/{inv.horror - old_h}恐惧")

        if inv.is_defeated:
            self.game_over = {"type": "lose", "message": "调查员被击败！"}
            events = self.event_logger.flush() if self.event_logger else []
            return {"success": True, "message": self.game_over["message"], "events": events}

        # Upkeep Phase
        self.action_log.append("--- 刷新阶段 ---")
        self.game.upkeep_phase.resolve()
        self.action_log.append("♻️ 就绪、抽1牌、+1资源")
        self._drain_effect_log()

        # Dissonant Voices cleanup
        if self.controller and self.controller.has_treachery("dissonant_voices"):
            self.controller.remove_treachery("dissonant_voices")
            self.action_log.append("🔇 不和谐的低语：回合结束弃掉")

        # New Round
        self.game.state.scenario.round_number += 1
        self.game.state.scenario.vars["frozen_in_fear_used"] = False
        self.game.state.scenario.vars["_action_seq"] = 0

        # Mythos Phase
        self.action_log.append("--- 神话阶段 ---")
        self.game.state.scenario.doom_on_agenda += 1
        self.controller._check_agenda_threshold()
        self._clear_game_over()
        if self.game_over:
            events = self.event_logger.flush() if self.event_logger else []
            return {"success": True, "message": self.game_over["message"], "events": events}

        # Encounter draw
        scen = self.game.state.scenario
        if not scen.encounter_deck:
            scen.encounter_deck = list(scen.encounter_discard)
            random.shuffle(scen.encounter_deck)
            scen.encounter_discard.clear()
            self.action_log.append("♻️ 遭遇弃牌堆洗回")

        if scen.encounter_deck:
            enc_id = scen.encounter_deck.pop(0)
            scen.encounter_discard.append(enc_id)
            # Store encounter card info for client display
            scen.vars["last_encounter"] = _lookup_encounter_card(enc_id, scen.vars.get("campaign", "core"))
            # Ward of Protection may have cancelled this encounter
            if scen.vars.get("cancelled_encounter") == enc_id:
                scen.vars.pop("cancelled_encounter", None)
                self.action_log.append("🛡️ 守护结界：取消遭遇")
                res = {"pending": False, "message": "cancelled"}
            else:
                res = self.controller.resolve_encounter_card(enc_id)
            if res.get("surge"):
                if scen.encounter_deck:
                    enc2 = scen.encounter_deck.pop(0)
                    scen.encounter_discard.append(enc2)
                    # Update last_encounter to show the surge card
                    scen.vars["last_encounter"] = _lookup_encounter_card(enc2, scen.vars.get("campaign", "core"))
                    self.controller.resolve_encounter_card(enc2)
            if res.get("pending"):
                events = self.event_logger.flush() if self.event_logger else []
                return {"success": True, "message": "需要做出选择", "events": events}

        if inv.is_defeated:
            self.game_over = {"type": "lose", "message": "调查员被遭遇击败！"}
            events = self.event_logger.flush() if self.event_logger else []
            return {"success": True, "message": self.game_over["message"], "events": events}

        self._clear_game_over()
        if self.game_over:
            events = self.event_logger.flush() if self.event_logger else []
            return {"success": True, "message": self.game_over["message"], "events": events}

        # New investigation phase
        inv.actions_remaining = 3
        self.game.state.scenario.current_phase = Phase.INVESTIGATION
        self.action_log.append(f"=== 第{self.game.state.scenario.round_number}轮 调查阶段 ===")
        # 调查阶段开始事件（黛西的典籍行动授予等）
        from backend.engine.event_bus import EventContext
        for inv_id in self.game.state.player_order:
            self.game.event_bus.emit(EventContext(
                game_state=self.game.state,
                event=GameEvent.INVESTIGATION_PHASE_BEGINS,
                investigator_id=inv_id,
            ))

        events = self.event_logger.flush() if self.event_logger else []
        self._drain_effect_log()
        return {"success": True, "message": "进入下一轮", "events": events}

    def _drain_effect_log(self) -> None:
        """Move card effect messages (GameState.effect_log) into the action log."""
        if self.game is None:
            return
        logs = self.game.state.effect_log
        if logs:
            self.action_log.extend(logs)
            logs.clear()

    # -------------------------------------------------------------------
    # Action handlers (ported from server_core.py)
    # -------------------------------------------------------------------

    def _resolve_choice(self, data: dict) -> dict:
        pc = self.game.state.scenario.vars.get("pending_choice")
        if not pc:
            return {"success": False, "message": "当前没有待选择项"}
        choice_id = data.get("choice_id")
        kind = pc.get("kind") or "encounter"
        self.game.state.scenario.vars.pop("pending_choice", None)

        if kind == "encounter":
            card_id = pc.get("card_id")
            self.controller.resolve_encounter_card(card_id, choice=choice_id)
            self._clear_game_over()
            return {"success": True, "message": "已选择"}

        # --- Zoey Samaras reactions on engage ---
        if kind == "zoey_reactions_on_engage":
            inv = self.game.state.get_investigator(pc.get("investigator_id"))
            if inv is None:
                return {"success": False, "message": "调查员不存在"}

            enemy_id = pc.get("enemy_id")
            cross_instance_id = pc.get("cross_instance_id")
            messages = []

            if choice_id == "none":
                self.action_log.append("🛡️ 佐伊·萨马拉斯：选择不触发Reaction能力")
                return {"success": True, "message": "未触发任何能力"}

            if choice_id in ("resource", "both"):
                # Gain 1 resource
                inv.resources += 1
                messages.append("获得1资源")
                self.action_log.append("💰 佐伊·萨马拉斯：获得1资源")

            if choice_id in ("cross", "both"):
                # Use cross: exhaust and spend 1 resource to deal 1 damage
                cross_instance = self.game.state.get_card_instance(cross_instance_id) if cross_instance_id else None
                if cross_instance and not cross_instance.exhausted and inv.resources >= 1:
                    inv.resources -= 1
                    cross_instance.exhausted = True

                    # Deal damage to the engaged enemy
                    enemy = self.game.state.get_card_instance(enemy_id)
                    if enemy:
                        enemy.damage += 1
                        enemy_data = self.game.state.get_card_data(enemy.card_id)
                        enemy_name = (enemy_data.name_cn or enemy_data.name) if enemy_data else "敌人"
                        messages.append(f"对{enemy_name}造成1伤害")
                        self.action_log.append(f"✝️ 佐伊的十字架：花费1资源，对【{enemy_name}】造成1伤害")
                    else:
                        messages.append("敌人已消失，无法造成伤害")
                else:
                    messages.append("十字架无法使用")

            return {"success": True, "message": "；".join(messages) if messages else "未触发效果"}

        if kind == "asset_old_book_of_lore":
            peek_cards: list[str] = list(pc.get("peek_cards") or [])
            if not peek_cards:
                return {"success": False, "message": "智慧古书��没有可选卡牌"}
            inv = self.game.state.get_investigator("player")
            chosen = choice_id if choice_id in peek_cards else peek_cards[0]
            rest = [c for c in peek_cards if c != chosen]
            inv.hand.append(chosen)
            inv.deck.extend(rest)
            cd = self.game.state.get_card_data(chosen)
            chosen_name = (cd.name_cn or "").strip() if cd else "（未翻译卡牌）"
            if not chosen_name:
                chosen_name = "（未翻译卡牌）"
            self.action_log.append(f"📚 智慧古书：你选择抽取【{chosen_name}】（其余{len(rest)}张置于牌库底）")
            return {"success": True, "message": "已抽牌"}

        # --- Mr. "Rook" step 1: search depth chosen → show cards ---
        if kind == "asset_mr_rook_depth":
            inv = self.game.state.get_investigator("player")
            depth = int(choice_id) if choice_id and choice_id.isdigit() else 3
            depth = min(depth, len(inv.deck))
            peek_cards = [inv.deck[i] for i in range(depth)]

            def card_label(cid: str) -> str:
                cd = self.game.state.get_card_data(cid)
                nm = (cd.name_cn or "").strip() if cd else "（未翻译卡牌）"
                return nm if nm else "（未翻译卡牌）"

            # Check for weaknesses
            weaknesses = []
            normals = []
            for cid in peek_cards:
                cd = self.game.state.get_card_data(cid)
                if cd and cd.type == CardType.TREACHERY:
                    weaknesses.append(cid)
                else:
                    normals.append(cid)

            options = [{"id": cid, "label": card_label(cid)} for cid in normals]
            self.game.state.scenario.vars["pending_choice"] = {
                "kind": "asset_mr_rook_pick",
                "peek_cards": peek_cards,
                "weaknesses": weaknesses,
                "prompt": f"<b>\"老千\"先生</b>：从牌库顶{depth}张中选择1张加入手牌",
                "options": options,
            }
            self.action_log.append(f"🔍 \"老千\"先生：查看牌库顶{depth}张，选择1张…")
            return {"success": True, "message": "需要做出选择"}

        # --- Mr. "Rook" step 2: card picked ---
        if kind == "asset_mr_rook_pick":
            inv = self.game.state.get_investigator("player")
            peek_cards: list[str] = list(pc.get("peek_cards") or [])
            weaknesses: list[str] = list(pc.get("weaknesses") or [])
            if not peek_cards:
                return {"success": False, "message": "没有可选卡牌"}
            chosen = choice_id if choice_id in peek_cards else peek_cards[0]
            # Remove chosen from deck
            if chosen in inv.deck:
                inv.deck.remove(chosen)
            inv.hand.append(chosen)
            cd = self.game.state.get_card_data(chosen)
            chosen_name = (cd.name_cn or chosen) if cd else chosen

            # Also draw 1 weakness if found
            weakness_drawn = None
            for w in weaknesses:
                if w != chosen and w in inv.deck:
                    inv.deck.remove(w)
                    inv.hand.append(w)
                    weakness_drawn = w
                    break

            # Shuffle deck
            random.shuffle(inv.deck)

            msg = f"\"老千\"先生：你选择抽取【{chosen_name}】"
            if weakness_drawn:
                wcd = self.game.state.get_card_data(weakness_drawn)
                wname = (wcd.name_cn or weakness_drawn) if wcd else weakness_drawn
                msg += f"，同时被迫抽取弱点【{wname}】"
            msg += "（牌库已洗牌）"
            self.action_log.append(f"🔍 {msg}")
            return {"success": True, "message": "已抽牌"}

        return {"success": False, "message": f"未知选择类型：{kind}"}

    def _advance_act(self, inv) -> dict:
        # 官方规则：推进事件是自由触发能力（free trigger），不消耗行动点
        if self.controller.advance_act("player"):
            self._clear_game_over()
            return {"success": True, "message": "事件推进"}
        return {"success": False, "message": "不满足推进条件（线索不足或无事件）"}

    def _resign(self) -> dict:
        rid = self.controller.resign()
        self._clear_game_over()
        return {"success": True, "message": f"撤退结局：{rid}"}

    def _locked_door_test(self, inv, data: dict) -> dict:
        if inv.actions_remaining <= 0:
            return {"success": False, "message": "没有行动点"}
        skill = data.get("skill")
        if skill not in {"combat", "agility"}:
            return {"success": False, "message": "skill 必须是 combat/agility"}
        attached = self.game.state.scenario.vars.get("treacheries", {}).get("locked_door", {}).get("attached_to")
        if not attached:
            return {"success": False, "message": "当前没有上锁的门"}

        inv.actions_remaining -= 1
        ok = {"success": False}

        def on_success(_r):
            ok["success"] = True
            self.controller.remove_treachery("locked_door")
            self.action_log.append("🚪 你打开了上锁的门（Locked Door弃掉）")

        self.game.skill_test_engine.run_test(
            investigator_id="player",
            skill_type=Skill.COMBAT if skill == "combat" else Skill.AGILITY,
            difficulty=4,
            committed_card_ids=data.get("committed_cards", []) or [],
            on_success=on_success,
            on_failure=lambda _r: None,
        )
        return {"success": ok["success"], "message": "开锁成功" if ok["success"] else "开锁失败"}

    def _discard_asset(self, inv, instance_id: str):
        """Remove an asset from play area and move its card_id to discard."""
        if instance_id in inv.play_area:
            inv.play_area.remove(instance_id)
        ci = self.game.state.get_card_instance(instance_id)
        if ci:
            inv.discard.append(ci.card_id)

    def _is_tome_asset(self, card_id: str) -> bool:
        """Check if a card has the Tome trait."""
        cd = self.game.state.get_card_data(card_id)
        if cd and hasattr(cd, 'traits') and cd.traits:
            return "tome" in [t.lower() for t in cd.traits]
        return False

    def _spend_activate_action(self, inv, card_id: str) -> bool:
        """Spend an action to activate an asset. Returns False if no actions available.

        For Tome assets, prefer using tome_actions_remaining (Daisy's free tome action).
        """
        is_tome = self._is_tome_asset(card_id)
        if is_tome and inv.tome_actions_remaining > 0:
            inv.tome_actions_remaining -= 1
            return True
        if inv.actions_remaining > 0:
            inv.actions_remaining -= 1
            return True
        return False

    # Cards whose effects are passive / reactive (no activated ability).
    _PASSIVE_CARDS: dict[str, str] = {
        "dr_milan_christopher_lv0": "被动：+1智力；调查成功后+1资源",
        "magnifying_glass_lv0": "被动：调查时+1智力",
        "beat_cop_lv0": "被动：+1战斗；可弃掉对敌人造成1伤害",
        "guard_dog_lv0": "被动：受到攻击时对敌人造成1伤害",
        "holy_rosary_lv0": "被动：+1意志",
        "leather_coat_lv0": "被动：+2生命值",
        "research_librarian_lv0": "被动：入场时搜索1张典籍",
        "laboratory_assistant_lv0": "被动：手牌上限+2；入场时抽2张",
        "arcane_studies_lv0": "花费资源：+1意志或+1智力",
        "hard_knocks_lv0": "花费资源：+1战斗或+1敏捷",
        "physical_training_lv0": "花费资源：+1意志或+1战斗",
        "dig_deep_lv0": "花费资源：+1意志或+1敏捷",
        "forbidden_knowledge_lv0": "被动：用秘密换取资源",
        "rabbits_foot_lv0": "被动：检定失败后抽1张",
        "scavenging_lv0": "被动：调查成功+2时回收弃牌堆支援",
        "pickpocketing_lv0": "被动：闪避成功后抽1张",
        "leo_de_luca_lv0": "被动：每回合+1行动",
        "leo_de_luca_lv1": "被动：每回合+1行动",
        "stray_cat_lv0": "被动：闪避时可弃掉自动成功",
        "arcane_initiate_lv0": "被动：刷新阶段搜索1张法术",
        "kukri_lv0": "武器：+1战斗",
        "ritual_candles_lv0": "被动：技能检定时+1",
    }

    def _mulligan(self, inv, data: dict) -> dict:
        """Opening hand mulligan: shuffle chosen cards back and redraw (once)."""
        scen = self.game.state.scenario
        if not scen.vars.get("mulligan_available"):
            return {"success": False, "message": "调度已不可用"}
        scen.vars.pop("mulligan_available", None)

        card_ids = [c for c in (data.get("card_ids") or []) if c in inv.hand]
        if card_ids:
            for cid in card_ids:
                inv.hand.remove(cid)
            inv.deck.extend(card_ids)
            random.shuffle(inv.deck)
            for _ in range(len(card_ids)):
                if inv.deck:
                    inv.hand.append(inv.deck.pop(0))
            self.action_log.append(f"🔁 调度：重抽 {len(card_ids)} 张手牌")
            return {"success": True, "message": f"调度：重抽 {len(card_ids)} 张"}
        self.action_log.append("🔁 保留初始手牌")
        return {"success": True, "message": "保留初始手牌"}

    def _activate_card(self, inv, data: dict) -> dict:
        """Generic activation channel: routes ACTIVATE_CARD to a card's
        declared activation method (CardImplementation.activations)."""
        instance_id = data.get("instance_id")
        activation_id = data.get("activation_id")
        if not instance_id or not activation_id:
            return {"success": False, "message": "缺少 instance_id / activation_id"}

        owned = instance_id in inv.play_area or instance_id in inv.threat_area
        if not owned:
            return {"success": False, "message": "该卡不在你的场上"}
        ci = self.game.state.get_card_instance(instance_id)
        if ci is None:
            return {"success": False, "message": "未找到卡牌实例"}

        impl_cls = self.game.card_registry.get_implementation(ci.card_id)
        if impl_cls is None:
            return {"success": False, "message": "该卡没有可用实现"}
        decl = next((a for a in getattr(impl_cls, "activations", [])
                     if a.get("id") == activation_id), None)
        if decl is None:
            return {"success": False, "message": "该卡没有此启动能力"}

        # Action cost
        actions_cost = int(decl.get("actions", 0) or 0)
        if actions_cost > inv.actions_remaining:
            return {"success": False, "message": f"需要{actions_cost}个行动"}

        # Get or create the impl instance
        impl = self.game.card_registry.active_instances.get(instance_id)
        if impl is None:
            impl = impl_cls(instance_id)
        method = getattr(impl, decl["method"], None)
        if method is None:
            return {"success": False, "message": "实现缺少方法"}

        cd = self.game.state.get_card_data(ci.card_id)
        name_cn = (cd.name_cn or cd.name) if cd else ci.card_id

        # Invoke with optional enemy target
        if decl.get("target") == "enemy":
            target_id = data.get("target_instance_id")
            if not target_id:
                engaged = [e for e in inv.threat_area]
                if len(engaged) == 1:
                    target_id = engaged[0]
                else:
                    return {"success": False, "message": "请指定目标敌人"}
            ok = method(self.game.state, inv.investigator_id, target_id)
        else:
            ok = method(self.game.state, inv.investigator_id)

        if not ok:
            return {"success": False, "message": f"{name_cn}：无法启动（条件不满足）"}

        if actions_cost:
            inv.actions_remaining -= actions_cost

        label = decl.get("label", activation_id)
        self.action_log.append(f"⚡ {name_cn}：{label}")
        return {"success": True, "message": f"{name_cn}：{label}"}

    def _activate_asset(self, inv, data: dict) -> dict:
        instance_id = data.get("instance_id")
        if not instance_id:
            return {"success": False, "message": "缺少 instance_id"}
        if instance_id not in inv.play_area:
            return {"success": False, "message": "该支援不在你的装备区"}
        ci = self.game.state.get_card_instance(instance_id)
        if not ci:
            return {"success": False, "message": "未找到支援实例"}

        card_id = ci.card_id

        # Passive-only cards: show status instead of trying to activate
        if card_id in self._PASSIVE_CARDS:
            cd = self.game.state.get_card_data(card_id)
            name_cn = (cd.name_cn or cd.name) if cd else card_id
            desc = self._PASSIVE_CARDS[card_id]
            status = "（已横置）" if ci.exhausted else ""
            return {"success": True, "message": f"{name_cn}{status}：{desc}"}

        if ci.exhausted:
            return {"success": False, "message": "该支援已消耗"}

        # Check action availability (tome actions preferred for Tome assets)
        if not self._spend_activate_action(inv, card_id):
            return {"success": False, "message": "没有行动点"}

        if card_id == "old_book_of_lore_lv0":
            if not inv.deck:
                return {"success": False, "message": "牌库为空，无法使用智慧古书"}
            ci.exhausted = True
            peek_n = min(3, len(inv.deck))
            peek_cards = [inv.deck.pop(0) for _ in range(peek_n)]

            def label(cid: str) -> str:
                cd = self.game.state.get_card_data(cid)
                nm = (cd.name_cn or "").strip() if cd else "（未翻译卡牌）"
                return nm if nm else "（未翻译卡牌）"

            options = [{"id": cid, "label": label(cid)} for cid in peek_cards]
            self.game.state.scenario.vars["pending_choice"] = {
                "kind": "asset_old_book_of_lore",
                "card_id": card_id,
                "asset_instance_id": instance_id,
                "peek_cards": peek_cards,
                "prompt": "<b>智慧古书</b>：查看牌库顶3张牌，选择1张加入手牌（其余置于牌库底）。",
                "options": options,
            }
            self.action_log.append("📚 智慧古书：查看牌库顶3张，等待选择…")
            return {"success": True, "message": "需要做出选择"}

        # --- Mr. "Rook" (free action: exhaust + spend 1 secret) ---
        if card_id == "mr_rook_lv0":
            # Free action — refund the action we just spent
            inv.actions_remaining += 1
            if ci.uses.get("secrets", 0) <= 0:
                return {"success": False, "message": "\"老千\"先生没有剩余秘密"}
            if not inv.deck:
                return {"success": False, "message": "牌库为空"}
            ci.exhausted = True
            ci.uses["secrets"] = ci.uses.get("secrets", 0) - 1
            # Step 1: choose search depth (3/6/9)
            options = []
            for n in [3, 6, 9]:
                if len(inv.deck) >= n or n == 3:
                    options.append({"id": str(n), "label": f"查看牌库顶{n}张"})
            self.game.state.scenario.vars["pending_choice"] = {
                "kind": "asset_mr_rook_depth",
                "asset_instance_id": instance_id,
                "prompt": "<b>\"老千\"先生</b>：选择搜索深度",
                "options": options,
            }
            self.action_log.append("🔍 \"老千\"先生：选择搜索深度…")
            return {"success": True, "message": "需要做出选择"}

        # --- Clarity of Mind (spend 1 charge: heal 1 horror) ---
        if card_id == "clarity_of_mind_lv0":
            if ci.uses.get("charges", 0) <= 0:
                return {"success": False, "message": "清明之心没有剩余充能"}
            ci.exhausted = True
            ci.uses["charges"] = ci.uses.get("charges", 0) - 1
            healed = min(1, inv.horror)
            inv.horror -= healed
            msg = f"清明之心：治愈{healed}点恐惧" if healed else "清明之心：当前没有恐惧可治愈"
            self.action_log.append(f"💜 {msg}")
            # Discard if no charges left
            if ci.uses.get("charges", 0) <= 0:
                self._discard_asset(inv, instance_id)
                self.action_log.append("💜 清明之心充能耗尽，弃置")
            return {"success": True, "message": msg}

        # --- Rite of Seeking (spend 1 charge: investigate with willpower) ---
        if card_id == "rite_of_seeking_lv0":
            if ci.uses.get("charges", 0) <= 0:
                return {"success": False, "message": "寻秘仪式没有剩余充能"}
            ci.exhausted = True
            ci.uses["charges"] = ci.uses.get("charges", 0) - 1
            loc = self.game.state.get_location(inv.location_id)
            if not loc:
                return {"success": False, "message": "当前地点无效"}
            difficulty = loc.card_data.shroud or 2
            result_ok = {"success": False}

            def on_success(_r):
                result_ok["success"] = True
                clues_to_gain = min(2, loc.clues)
                loc.clues -= clues_to_gain
                inv.clues += clues_to_gain
                self.action_log.append(f"🔮 寻秘仪式成功！发现{clues_to_gain}条线索")

            def on_failure(_r):
                self.action_log.append("🔮 寻秘仪式失败")

            self.game.skill_test_engine.run_test(
                investigator_id="player",
                skill_type=Skill.WILLPOWER,
                difficulty=difficulty,
                committed_card_ids=[],
                on_success=on_success,
                on_failure=on_failure,
            )
            if ci.uses.get("charges", 0) <= 0:
                self._discard_asset(inv, instance_id)
                self.action_log.append("🔮 寻秘仪式充能耗尽，弃置")
            return {"success": result_ok["success"],
                    "message": "调查成功" if result_ok["success"] else "调查失败"}

        # --- Liquid Courage (spend 1 supply: heal 1 horror + test) ---
        if card_id == "liquid_courage_lv0":
            if ci.uses.get("supplies", 0) <= 0:
                return {"success": False, "message": "液体勇气没有剩余补给"}
            ci.uses["supplies"] = ci.uses.get("supplies", 0) - 1
            healed = min(1, inv.horror)
            inv.horror -= healed
            result_ok = {"extra_heal": False}

            def on_success(_r):
                result_ok["extra_heal"] = True
                extra = min(1, inv.horror)
                inv.horror -= extra
                self.action_log.append(f"🍺 液体勇气：意志检定成功，额外治愈{extra}点恐惧")

            def on_failure(_r):
                if inv.hand:
                    discarded = inv.hand.pop(random.randint(0, len(inv.hand) - 1))
                    inv.discard.append(discarded)
                    cd = self.game.state.get_card_data(discarded)
                    nm = (cd.name_cn or discarded) if cd else discarded
                    self.action_log.append(f"🍺 液体勇气：意志检定失败，随机弃置【{nm}】")
                else:
                    self.action_log.append("🍺 液体勇气：意志检定失败（手牌为空）")

            self.game.skill_test_engine.run_test(
                investigator_id="player",
                skill_type=Skill.WILLPOWER,
                difficulty=2,
                committed_card_ids=[],
                on_success=on_success,
                on_failure=on_failure,
            )
            msg = f"液体勇气：治愈{healed}点恐惧"
            self.action_log.append(f"🍺 {msg}")
            if ci.uses.get("supplies", 0) <= 0:
                self._discard_asset(inv, instance_id)
                self.action_log.append("🍺 液体勇气补给耗尽，弃置")
            return {"success": True, "message": msg}

        # Weapons: use in FIGHT action, not direct activation
        cd = self.game.state.get_card_data(card_id)
        if cd and "weapon" in [t.lower() for t in (cd.traits or [])]:
            return {"success": True, "message": f"武器请通过攻击敌人时选择使用"}

        return {"success": False, "message": "该支援暂不支持激活"}

    def _normal_action(self, inv, act: str, data: dict) -> dict:
        try:
            enum_act = Action[act]
        except Exception:
            return {"success": False, "message": f"未知 action: {act}"}

        # Treachery checks
        if enum_act == Action.PLAY and self.controller and self.controller.has_treachery("dissonant_voices"):
            return {"success": False, "message": "不和谐的低语：本轮不能打出支援/事件"}

        if enum_act in {Action.MOVE, Action.FIGHT, Action.EVADE} and self.controller and self.controller.has_treachery("frozen_in_fear"):
            if not self.game.state.scenario.vars.get("frozen_in_fear_used", False):
                if inv.actions_remaining <= 1:
                    return {"success": False, "message": "恐惧冻结：需要额外1行动"}
                inv.actions_remaining -= 1
                self.game.state.scenario.vars["frozen_in_fear_used"] = True
                self.action_log.append("🥶 恐惧冻结：支付额外1行动")

        if enum_act == Action.INVESTIGATE:
            attached = self.game.state.scenario.vars.get("treacheries", {}).get("locked_door", {}).get("attached_to")
            if attached and attached == inv.location_id:
                return {"success": False, "message": "上锁的门：该地点无法调查"}

        # Obscuring Fog
        fog_loc = self.game.state.scenario.vars.get("treacheries", {}).get("obscuring_fog", {}).get("attached_to")
        shroud_bump = False
        if enum_act == Action.INVESTIGATE and fog_loc == inv.location_id:
            loc = self.game.state.get_location(inv.location_id)
            if loc:
                loc.card_data.shroud = (loc.card_data.shroud or 0) + 2
                shroud_bump = True

        played_card_id = data.get("card_id") if enum_act == Action.PLAY else None
        before_hand = len(inv.hand)
        before_deck = len(inv.deck)
        before_discard = len(inv.discard)

        try:
            ok = self.game.action_resolver.perform_action(
                "player", enum_act,
                **{k: v for k, v in data.items() if k != "action"}
            )
        finally:
            if shroud_bump:
                loc = self.game.state.get_location(inv.location_id)
                if loc:
                    loc.card_data.shroud = max(0, (loc.card_data.shroud or 0) - 2)

        # Flush any card-generated messages (e.g. search results) to the action log
        self._flush_action_messages()

        if not ok:
            return {"success": False, "message": "行动失败"}

        # --- Detailed action logging ---
        if played_card_id:
            cd = self.game.state.get_card_data(played_card_id)
            name_cn = (cd.name_cn or "").strip() if cd else "（未翻译卡牌）"
            if not name_cn:
                name_cn = "（未翻译卡牌）"
            delta_hand = len(inv.hand) - before_hand
            delta_deck = len(inv.deck) - before_deck
            delta_discard = len(inv.discard) - before_discard
            self.action_log.append(f"🃏 打出：{name_cn}（手牌{delta_hand:+d}，牌库{delta_deck:+d}，弃牌{delta_discard:+d}）")
        elif enum_act == Action.MOVE:
            loc_id = data.get("location_id", "")
            loc = self.game.state.get_location(loc_id)
            loc_name = (loc.card_data.name_cn or loc.card_data.name) if loc else loc_id
            self.action_log.append(f"🚶 移动到：{loc_name}")
        elif enum_act == Action.INVESTIGATE:
            self._log_skill_test("🔍 调查")
        elif enum_act == Action.FIGHT:
            eid = data.get("enemy_instance_id", "")
            ci = self.game.state.get_card_instance(eid) if eid else None
            cd = self.game.state.get_card_data(ci.card_id) if ci else None
            enemy_name = (cd.name_cn or cd.name) if cd else "敌人"
            self._log_skill_test(f"⚔️ 攻击 {enemy_name}")
        elif enum_act == Action.EVADE:
            eid = data.get("enemy_instance_id", "")
            ci = self.game.state.get_card_instance(eid) if eid else None
            cd = self.game.state.get_card_data(ci.card_id) if ci else None
            enemy_name = (cd.name_cn or cd.name) if cd else "敌人"
            self._log_skill_test(f"🏃 闪避 {enemy_name}")
        elif enum_act == Action.ENGAGE:
            self.action_log.append("🎯 交战")
        elif enum_act == Action.DRAW:
            self.action_log.append("🃏 抽牌")
        elif enum_act == Action.RESOURCE:
            self.action_log.append(f"◆ 获取资源 → {inv.resources}")

        return {"success": True, "message": "行动成功"}

    def _log_skill_test(self, prefix: str) -> None:
        """Log the most recent skill test result with chaos token details."""
        st = self.game.skill_test_engine.current_test if self.game else None
        # The test already completed, so check the event logger for the result
        # We read from the last SkillTestResult stored on the engine
        result = getattr(self.game.skill_test_engine, '_last_result', None) if self.game else None
        if result is None:
            # Try to get from the action resolver's last test
            result = getattr(self.game.action_resolver, '_last_skill_test_result', None) if self.game else None
        if result is None:
            self.action_log.append(prefix)
            return

        token_name = result.token.value if result.token else "?"
        TOKEN_NAMES = {
            "+1": "+1", "0": "0", "-1": "-1", "-2": "-2", "-3": "-3",
            "-4": "-4", "-5": "-5", "-6": "-6", "-7": "-7", "-8": "-8",
            "skull": "💀骷髅", "cultist": "👤邪���徒", "tablet": "📋石板",
            "elder_thing": "🐙远古", "auto_fail": "❌自动失败",
            "elder_sign": "✡长老印记", "bless": "🙏祝福", "curse": "💀诅咒",
        }
        token_display = TOKEN_NAMES.get(token_name, token_name)
        mod = result.token_modifier
        mod_str = f"{mod:+d}" if mod != 0 else "0"
        result_str = "✅成功" if result.success else "❌失败"
        if result.auto_fail:
            result_str = "❌自动失败"

        # 投入的技能卡（名称 + 图标数）
        committed = getattr(self.game.skill_test_engine, '_committed_card_ids', None) or []
        commit_str = ""
        if committed:
            names = "、".join(self.game.state.card_name(c) for c in committed)
            commit_str = f"（投入：{names}，+{result.committed_icons}）"

        detail = f"[{token_display}({mod_str})] 技能{result.modified_skill} vs 难度{result.difficulty} → {result_str}"
        self.action_log.append(f"{prefix}{commit_str} {detail}")

    def _flush_action_messages(self) -> None:
        """Move card-generated messages from scenario.vars to the action log."""
        msgs = self.game.state.scenario.vars.pop("action_messages", None)
        if msgs:
            for msg in msgs:
                self.action_log.append(msg)
