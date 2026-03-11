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
from backend.models.enums import Action, CardType, Phase, PlayerClass, SlotType, Skill
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

DECK_PRESETS: dict[str, dict] = {
    "roland_starter": {
        "name_cn": "罗兰·班克斯（入门战斗）",
        "investigator_id": "roland_banks",
        "cards": [
            "machete_lv0", "45_automatic_lv0", "flashlight_lv0",
            "emergency_cache_lv0", "beat_cop_lv0", "guard_dog_lv0",
            "first_aid_lv0", "dodge_lv0", "evidence_lv0", "vicious_blow_lv0",
            "guts_lv0", "overpower_lv0", "perception_lv0",
            "manual_dexterity_lv0", "unexpected_courage_lv0",
        ],
    },
    "daisy_starter": {
        "name_cn": "黛西·沃克（入门调查）",
        "investigator_id": "daisy_walker",
        "cards": [
            "magnifying_glass_lv0", "old_book_of_lore_lv0", "medical_texts_lv0",
            "dr_milan_christopher_lv0", "research_librarian_lv0",
            "working_a_hunch_lv0", "deduction_lv0", "perception_lv0",
            "guts_lv0", "unexpected_courage_lv0", "preposterous_sketches_lv0",
            "inquiring_mind_lv0", "mind_over_matter_lv0", "shortcut_lv0",
            "knife_lv0",
        ],
    },
    "skids_starter": {
        "name_cn": "斯基兹·奥图尔（入门机动）",
        "investigator_id": "skids_otoole",
        "cards": [
            "switchblade_lv0", "forty_one_derringer_lv0", "burglary_lv0",
            "pickpocketing_lv0", "sneak_attack_lv0", "elusive_lv0",
            "opportunist_lv0", "hard_knocks_lv0", "leo_de_luca_lv0",
            "emergency_cache_lv0", "manual_dexterity_lv0", "overpower_lv0",
            "perception_lv0", "unexpected_courage_lv0", "knife_lv0",
        ],
    },
    "agnes_starter": {
        "name_cn": "艾格尼丝·贝克（入门法术）",
        "investigator_id": "agnes_baker",
        "cards": [
            "shrivelling_lv0", "holy_rosary_lv0", "arcane_studies_lv0",
            "ward_of_protection_lv0", "forbidden_knowledge_lv0",
            "drawn_to_the_flame_lv0", "fearless_lv0", "blinding_light_lv0",
            "guts_lv0", "unexpected_courage_lv0", "emergency_cache_lv0",
            "perception_lv0", "manual_dexterity_lv0", "knife_lv0",
            "flashlight_lv0",
        ],
    },
    "wendy_starter": {
        "name_cn": "温蒂·亚当斯（入门生存）",
        "investigator_id": "wendy_adams",
        "cards": [
            "baseball_bat_lv0", "rabbits_foot_lv0", "leather_coat_lv0",
            "lucky_lv0", "look_what_i_found_lv0", "stray_cat_lv0",
            "scavenging_lv0", "survival_instinct_lv0", "dig_deep_lv0",
            "manual_dexterity_lv0", "guts_lv0", "overpower_lv0",
            "perception_lv0", "unexpected_courage_lv0", "emergency_cache_lv0",
        ],
    },
}


# ---------------------------------------------------------------------------
# Card loading helpers
# ---------------------------------------------------------------------------

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
                text=data.get("text_cn") or data.get("text") or "",
                health=data.get("health"),
                sanity=data.get("sanity"),
                pack=data.get("pack") or "",
                unique=bool(data.get("unique") or False),
                fast=bool(data.get("fast") or False),
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
        seed: int = 42,
    ) -> dict:
        """Initialize a single-player game (multi-player setup in Phase 4)."""
        self.action_log = []
        self.game_over = None

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

        # Investigator
        inv_def = INVESTIGATORS.get(investigator_id) or INVESTIGATORS["daisy_walker"]
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
        g.register_card_data(inv_data)

        # Deck
        deck_ids: list[str] = []
        if deck_preset and deck_preset in DECK_PRESETS:
            for cid in DECK_PRESETS[deck_preset]["cards"]:
                deck_ids.extend([cid, cid])
        else:
            for preset_id, preset in DECK_PRESETS.items():
                if preset.get("investigator_id") == investigator_id:
                    for cid in preset["cards"]:
                        deck_ids.extend([cid, cid])
                    break

        deck_ids = [cid for cid in deck_ids if g.state.get_card_data(cid) is not None]
        if len(deck_ids) < 30:
            deck_ids += ["filler"] * (30 - len(deck_ids))
        elif len(deck_ids) > 30:
            deck_ids = deck_ids[:30]

        random.shuffle(deck_ids)

        # Scenario
        apply_scenario_to_game(g, scenario_id, seed=seed)
        scen = load_scenario_definition(scenario_id)
        g.add_investigator("player", inv_data, deck=deck_ids, starting_location=scen["start_location"])
        g.setup()

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

        # Flush any previous events
        if self.event_logger:
            self.event_logger.flush()

        # Resolve pending choice
        if act == "RESOLVE_CHOICE":
            result = self._resolve_choice(data)
        elif act == "ADVANCE_ACT":
            result = self._advance_act(inv)
        elif act == "RESIGN":
            result = self._resign()
        elif act == "LOCKED_DOOR_TEST":
            result = self._locked_door_test(inv, data)
        elif act == "ACTIVATE_ASSET":
            result = self._activate_asset(inv, data)
        else:
            result = self._normal_action(inv, act, data)

        # Capture events for animation
        events = self.event_logger.flush() if self.event_logger else []
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
            res = self.controller.resolve_encounter_card(enc_id)
            if res.get("surge"):
                if scen.encounter_deck:
                    enc2 = scen.encounter_deck.pop(0)
                    scen.encounter_discard.append(enc2)
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

        events = self.event_logger.flush() if self.event_logger else []
        return {"success": True, "message": "进入下一轮", "events": events}

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

        return {"success": False, "message": f"未知选择类型：{kind}"}

    def _advance_act(self, inv) -> dict:
        if inv.actions_remaining <= 0:
            return {"success": False, "message": "没有行动点"}
        if self.controller.advance_act("player"):
            inv.actions_remaining -= 1
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

    def _activate_asset(self, inv, data: dict) -> dict:
        if inv.actions_remaining <= 0:
            return {"success": False, "message": "没有行动点"}
        instance_id = data.get("instance_id")
        if not instance_id:
            return {"success": False, "message": "缺少 instance_id"}
        if instance_id not in inv.play_area:
            return {"success": False, "message": "该支援不在你的装备区"}
        ci = self.game.state.get_card_instance(instance_id)
        if not ci:
            return {"success": False, "message": "未找到支援实例"}
        if ci.exhausted:
            return {"success": False, "message": "该支援已消耗"}

        card_id = ci.card_id
        if card_id == "old_book_of_lore_lv0":
            if not inv.deck:
                return {"success": False, "message": "牌库为空，无法使用智慧古书"}
            inv.actions_remaining -= 1
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

        if played_card_id:
            cd = self.game.state.get_card_data(played_card_id)
            name_cn = (cd.name_cn or "").strip() if cd else "（未翻译卡牌）"
            if not name_cn:
                name_cn = "（未翻译卡牌）"
            delta_hand = len(inv.hand) - before_hand
            delta_deck = len(inv.deck) - before_deck
            delta_discard = len(inv.discard) - before_discard
            self.action_log.append(f"🃏 打出：{name_cn}（手牌{delta_hand:+d}，牌库{delta_deck:+d}，弃牌{delta_discard:+d}）")

        return {"success": True, "message": "行动成功"}

    def _flush_action_messages(self) -> None:
        """Move card-generated messages from scenario.vars to the action log."""
        msgs = self.game.state.scenario.vars.pop("action_messages", None)
        if msgs:
            for msg in msgs:
                self.action_log.append(msg)
