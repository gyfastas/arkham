#!/usr/bin/env python3
"""Core campaign scenario server (The Gathering / Midnight Masks / Devourer Below).

This server reuses `frontend/scenario.html` and exposes a small JSON API:
- GET  /api/state
- POST /api/setup        {"scenario_id": "the_gathering"|...}
- POST /api/action       {"action": "INVESTIGATE"|..., ...}
- POST /api/end-turn

目标：让你能实际"玩一遍"核心剧本，并且所有核心剧本遭遇诡计都有结算覆盖。
"""

from __future__ import annotations

import json
import random
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.engine.game import Game
from backend.models.enums import Action, CardType, Phase, PlayerClass, SlotType
from backend.models.state import CardData, SkillValues
from backend.scenarios.official_core import apply_scenario_to_game, load_scenario_definition, ScenarioController
from server.state_serializer import serialize_game_state as _serialize_game_state


# Global state
game: Game | None = None
controller: ScenarioController | None = None
action_log: list[str] = []
game_over: dict | None = None  # {"type":"win"|"lose", "message":"..."}

# Cache: used by deck builder in frontend before game starts
_PLAYER_CARD_CATALOG_CACHE: list[dict] | None = None
_ALL_CARDS_CN_INDEX: dict[tuple[str, str, str, int], dict] | None = None

# Card metadata (signature/weakness/deck limits) loaded from `data/player_cards/**.json`
_CARD_META: dict[str, dict] = {}


def _card_meta(card_id: str) -> dict:
    return _CARD_META.get(card_id) or {}


def _deck_role(card_id: str) -> str:
    """Return deck role for deckbuilding UI/validation.

    Roles:
    - normal: counts toward 30
    - signature: investigator-specific (does not count)
    - weakness: weakness/basic weakness (does not count)
    - placeholder: placeholder weakness (does not count, not added to deck)
    """
    m = _card_meta(card_id)
    if m.get("placeholder"):
        return "placeholder"
    if m.get("weakness"):
        return "weakness"
    if m.get("signature"):
        return "signature"
    return "normal"


def _load_investigator_profile(investigator_id: str) -> dict:
    """Load investigator deckbuilding info from `data/investigators/*.json` if present."""
    p = PROJECT_ROOT / "data" / "investigators" / f"{investigator_id}.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _card_name_cn(gs, card_id: str) -> str:
    if not card_id:
        return "（未知卡牌）"
    cd = gs.get_card_data(card_id) if gs else None
    nm = (cd.name_cn or "").strip() if cd else ""
    return nm if nm else "（未翻译卡牌）"


def _loc_name_cn(gs, loc_id: str) -> str:
    if not loc_id:
        return "（未知地点）"
    loc = gs.get_location(loc_id) if gs else None
    nm = (loc.card_data.name_cn or "").strip() if loc and loc.card_data else ""
    return nm if nm else loc_id


def _enemy_name_cn(gs, enemy_instance_id: str) -> str:
    if not enemy_instance_id:
        return "（未知敌人）"
    ci = gs.get_card_instance(enemy_instance_id) if gs else None
    if not ci:
        return "（未知敌人）"
    return _card_name_cn(gs, ci.card_id)


def _attach_system_loggers(g: Game) -> None:
    """Attach event-bus loggers that write to `action_log`.

    Goal: Make log systematic and complete (draw, clues, resources, move, combat damage/defeat).
    """
    from backend.models.enums import GameEvent, TimingPriority, Action as ActEnum, Skill as SkillEnum

    bus = g.event_bus

    # Avoid double-register when resetting game
    if g.state.scenario.vars.get("_sys_loggers_attached"):
        return
    g.state.scenario.vars["_sys_loggers_attached"] = True

    def phase_cn(gs) -> str:
        try:
            p = gs.scenario.current_phase.name
        except Exception:
            p = ""
        return {
            "SETUP": "准备",
            "MYTHOS": "神话",
            "INVESTIGATION": "调查",
            "ENEMY": "敌人",
            "UPKEEP": "刷新",
        }.get(p, p or "?")

    def _action_seq(gs) -> int:
        try:
            return int(gs.scenario.vars.get("_action_seq") or 0)
        except Exception:
            return 0

    def _set_action_seq(gs, n: int) -> None:
        try:
            gs.scenario.vars["_action_seq"] = int(n)
        except Exception:
            pass

    def _next_action_seq(gs) -> int:
        n = _action_seq(gs) + 1
        _set_action_seq(gs, n)
        return n

    def _log(ctx, category: str, msg: str, *, seq: int | None = None) -> None:
        gs = ctx.game_state
        rnd = getattr(gs.scenario, "round_number", 0)
        ph = phase_cn(gs)
        if seq is None:
            seq = _action_seq(gs)
        tag = f"行动#{seq}" if seq else "系统"
        action_log.append(f"[R{rnd} {ph}][{tag}][{category}] {msg}")

    def action_cn(a: ActEnum | None) -> str:
        if a is None:
            return "行动"
        return {
            ActEnum.INVESTIGATE: "调查",
            ActEnum.MOVE: "移动",
            ActEnum.DRAW: "抽牌",
            ActEnum.RESOURCE: "资源",
            ActEnum.FIGHT: "战斗",
            ActEnum.EVADE: "闪避",
            ActEnum.PLAY: "打出",
            ActEnum.ENGAGE: "交战",
        }.get(a, a.name)

    def skill_cn(s: SkillEnum | None) -> str:
        if s is None:
            return "检定"
        return {
            SkillEnum.WILLPOWER: "意志",
            SkillEnum.INTELLECT: "智力",
            SkillEnum.COMBAT: "战斗",
            SkillEnum.AGILITY: "敏捷",
        }.get(s, s.name)

    def chaos_token_label(t) -> str:
        """Return a user-friendly CN label for a chaos token."""
        if t is None:
            return "?"
        v = getattr(t, "value", None)
        raw = v if isinstance(v, str) else str(t)
        return {
            "skull": "骷髅",
            "cultist": "教徒",
            "tablet": "石板",
            "elder_thing": "古神",
            "elder_sign": "上古印记",
            "auto_fail": "自动失败",
            "bless": "祝福",
            "curse": "诅咒",
            "frost": "霜",
        }.get(raw, raw)

    def _skill_icon_breakdown_for_commit(gs, *, skill_type: SkillEnum | None, card_id: str) -> tuple[int, str]:
        """Return (icons_counted, detail_str) for commit display.

        Counted icons follow our engine rule: matching skill + wild.
        """
        cd = gs.get_card_data(card_id) if gs else None
        icons = dict(getattr(cd, "skill_icons", None) or {})
        if not icons or skill_type is None:
            return (0, "")
        key = getattr(skill_type, "value", None)
        if not isinstance(key, str):
            return (0, "")
        match = int(icons.get(key, 0) or 0)
        wild = int(icons.get("wild", 0) or 0)
        total = max(0, match) + max(0, wild)
        parts: list[str] = []
        if match:
            parts.append(f"{skill_cn(skill_type)}+{match}")
        if wild:
            parts.append(f"万用+{wild}")
        return (total, " ".join(parts))

    # ======== core action logging ========
    def on_action_performed(ctx):
        gs = ctx.game_state
        seq = _next_action_seq(gs)
        inv = gs.get_investigator(ctx.investigator_id) if gs else None
        left = inv.actions_remaining if inv else 0
        _log(ctx, "行动", f"{action_cn(ctx.action)}（剩余行动：{left}）", seq=seq)

    def on_draw(ctx):
        cid = (ctx.extra or {}).get("card_id")
        inv = ctx.game_state.get_investigator(ctx.investigator_id) if ctx.game_state else None
        left = len(inv.deck) if inv else 0
        _log(ctx, "抽牌", f"{_card_name_cn(ctx.game_state, cid)}（牌库剩余：{left}）")

    def on_clue(ctx):
        loc_cn = _loc_name_cn(ctx.game_state, ctx.location_id)
        inv = ctx.game_state.get_investigator(ctx.investigator_id) if ctx.game_state else None
        now = inv.clues if inv else 0
        _log(ctx, "线索", f"在【{loc_cn}】发现{ctx.amount}线索（当前线索：{now}）")

    def on_res_gain(ctx):
        inv = ctx.game_state.get_investigator(ctx.investigator_id) if ctx.game_state else None
        now = inv.resources if inv else 0
        _log(ctx, "资源", f"+{ctx.amount}（当前资源：{now}）")

    def on_res_spent(ctx):
        inv = ctx.game_state.get_investigator(ctx.investigator_id) if ctx.game_state else None
        now = inv.resources if inv else 0
        _log(ctx, "资源", f"-{ctx.amount}（当前资源：{now}）")

    def on_move(ctx):
        loc_cn = _loc_name_cn(ctx.game_state, ctx.location_id)
        _log(ctx, "移动", f"进入【{loc_cn}】")

    def on_engage(ctx):
        _log(ctx, "交战", f"{_enemy_name_cn(ctx.game_state, ctx.enemy_id)}")

    def on_damage(ctx):
        enemy = _enemy_name_cn(ctx.game_state, ctx.target)
        ci = ctx.game_state.get_card_instance(ctx.target) if ctx.game_state else None
        cd = ctx.game_state.get_card_data(ci.card_id) if (ctx.game_state and ci) else None
        hp = (cd.enemy_health or 0) if cd else 0
        cur = ci.damage if ci else 0
        _log(ctx, "伤害", f"{enemy} -{ctx.amount}（{cur}/{hp}）")

    def on_enemy_defeated(ctx):
        _log(ctx, "击败", f"{_enemy_name_cn(ctx.game_state, ctx.target)}")

    # ======== skill test logging ========
    def st_begins(ctx):
        inv = ctx.game_state.get_investigator(ctx.investigator_id) if ctx.game_state else None
        base = inv.get_skill(ctx.skill_type) if inv and ctx.skill_type else 0
        _log(ctx, "检定", f"开始{skill_cn(ctx.skill_type)}检定（难度{ctx.difficulty}，基础{base}）")

    def st_commit(ctx):
        committed = list(ctx.committed_cards or [])
        if not committed:
            _log(ctx, "检定", "投入：无（+0）")
            return

        items: list[str] = []
        total = 0
        for cid in committed:
            nm = _card_name_cn(ctx.game_state, cid)
            n, detail = _skill_icon_breakdown_for_commit(ctx.game_state, skill_type=ctx.skill_type, card_id=cid)
            total += n
            if detail:
                items.append(f"{nm}（{detail}）")
            else:
                items.append(f"{nm}（+0）")

        # Prefer engine computed amount (may be modified by effects), but still show our breakdown.
        amt = int(ctx.amount or 0)
        if amt != total:
            _log(ctx, "检定", f"投入：{'、'.join(items)}（合计+{amt}；明细合计+{total}）")
        else:
            _log(ctx, "检定", f"投入：{'、'.join(items)}（合计+{amt}）")

    def st_token_reveal(ctx):
        _log(ctx, "检定", f"揭示混沌标记：{chaos_token_label(ctx.chaos_token)}")

    def st_token_resolve(ctx):
        # AUTO_FAIL has amount 0 but means special
        tok = chaos_token_label(ctx.chaos_token)
        if tok == "自动失败":
            _log(ctx, "检定", "标记效果：自动失败")
            return

        amt = int(ctx.amount or 0)
        # Symbol tokens are scenario-dependent; engine currently treats most as 0.
        if tok in {"骷髅", "教徒", "石板", "古神", "上古印记"} and amt == 0:
            _log(ctx, "检定", f"标记修正：{amt:+d}（{tok}：符号标记效果未实现，暂按0）")
        else:
            _log(ctx, "检定", f"标记修正：{amt:+d}")

    def st_value(ctx):
        # Provide a more systematic breakdown when possible.
        st = None
        try:
            st = g.skill_test_engine.current_test
        except Exception:
            st = None

        if st and getattr(st, "auto_fail", False):
            _log(ctx, "检定", f"最终值：0（自动失败） vs 难度{ctx.difficulty}")
            return

        if st:
            base = int(getattr(st, "base_skill", 0) or 0)
            committed = int(getattr(st, "committed_icons", 0) or 0)
            token_mod = int(getattr(st, "token_modifier", 0) or 0)
            final = int(ctx.amount or 0)
            _log(ctx, "检定", f"最终值：{base}+{committed}{token_mod:+d}={final} vs 难度{ctx.difficulty}")
        else:
            _log(ctx, "检定", f"最终值：{ctx.amount} vs 难度{ctx.difficulty}")

    def st_result(ctx):
        diff = int(ctx.difficulty or 0)
        mod = int(ctx.modified_skill or 0)
        margin = mod - diff
        ok = "成功" if ctx.success else "失败"
        _log(ctx, "检定", f"结果：{ok}（差值{margin:+d}）")

    def st_ends(ctx):
        _log(ctx, "检定", "检定结束")

    bus.register(GameEvent.ACTION_PERFORMED, on_action_performed, priority=TimingPriority.AFTER)
    bus.register(GameEvent.CARD_DRAWN, on_draw, priority=TimingPriority.AFTER)
    bus.register(GameEvent.CLUE_DISCOVERED, on_clue, priority=TimingPriority.AFTER)
    bus.register(GameEvent.RESOURCES_GAINED, on_res_gain, priority=TimingPriority.AFTER)
    bus.register(GameEvent.RESOURCES_SPENT, on_res_spent, priority=TimingPriority.AFTER)
    bus.register(GameEvent.MOVE_ACTION_INITIATED, on_move, priority=TimingPriority.AFTER)
    bus.register(GameEvent.ENEMY_ENGAGED, on_engage, priority=TimingPriority.AFTER)
    bus.register(GameEvent.DAMAGE_DEALT, on_damage, priority=TimingPriority.AFTER)
    bus.register(GameEvent.ENEMY_DEFEATED, on_enemy_defeated, priority=TimingPriority.AFTER)

    bus.register(GameEvent.SKILL_TEST_BEGINS, st_begins, priority=TimingPriority.AFTER)
    bus.register(GameEvent.SKILL_TEST_COMMIT, st_commit, priority=TimingPriority.AFTER)
    bus.register(GameEvent.CHAOS_TOKEN_REVEALED, st_token_reveal, priority=TimingPriority.AFTER)
    bus.register(GameEvent.CHAOS_TOKEN_RESOLVED, st_token_resolve, priority=TimingPriority.AFTER)
    bus.register(GameEvent.SKILL_VALUE_DETERMINED, st_value, priority=TimingPriority.AFTER)
    bus.register(GameEvent.SKILL_TEST_SUCCESSFUL, st_result, priority=TimingPriority.AFTER)
    bus.register(GameEvent.SKILL_TEST_FAILED, st_result, priority=TimingPriority.AFTER)
    bus.register(GameEvent.SKILL_TEST_ENDS, st_ends, priority=TimingPriority.AFTER)


def _has_zh(text: str) -> bool:
    return any("\u4e00" <= ch <= "\u9fff" for ch in (text or ""))


def _load_all_cards_cn_index() -> dict[tuple[str, str, str, int], dict]:
    """Index `all_cards.json` by (english_name, type_code, faction_code, xp).

    Note: `all_cards.json` is exported from ArkhamDB with CN (often Traditional)
    `name` and `text` fields. We use it as the Chinese source of truth.
    """
    global _ALL_CARDS_CN_INDEX
    if _ALL_CARDS_CN_INDEX is not None:
        return _ALL_CARDS_CN_INDEX

    p = PROJECT_ROOT / "all_cards.json"
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        _ALL_CARDS_CN_INDEX = {}
        return _ALL_CARDS_CN_INDEX

    idx: dict[tuple[str, str, str, int], dict] = {}
    for c in raw if isinstance(raw, list) else []:
        real_name = (c.get("real_name") or c.get("original_name") or "").strip().lower()
        type_code = (c.get("type_code") or "").strip().lower()
        faction_code = (c.get("faction_code") or "").strip().lower()
        xp_raw = c.get("xp")
        try:
            xp = int(xp_raw or 0)
        except Exception:
            xp = 0

        if not real_name or not type_code:
            continue
        # Only index entries that have Chinese text content
        text_cn = (c.get("text") or "").strip()
        if not _has_zh(text_cn):
            continue

        key = (real_name, type_code, faction_code or "neutral", xp)
        idx[key] = c

    _ALL_CARDS_CN_INDEX = idx
    return _ALL_CARDS_CN_INDEX


def _lookup_text_cn_from_all_cards(*, name_en: str, type_code: str, faction_code: str, level: int) -> str:
    idx = _load_all_cards_cn_index()
    real_name = (name_en or "").strip().lower()
    t = (type_code or "").strip().lower()
    f = (faction_code or "neutral").strip().lower() or "neutral"
    try:
        xp = int(level or 0)
    except Exception:
        xp = 0

    # Exact match
    c = idx.get((real_name, t, f, xp))
    if c and _has_zh(c.get("text") or ""):
        return (c.get("text") or "").strip()

    # Some neutral cards have faction_code empty in source; try neutral fallback
    c = idx.get((real_name, t, "neutral", xp))
    if c and _has_zh(c.get("text") or ""):
        return (c.get("text") or "").strip()

    # Last resort: ignore faction (search few candidates)
    for (rn, tt, ff, xx), cc in idx.items():
        if rn == real_name and tt == t and xx == xp:
            text = (cc.get("text") or "").strip()
            if _has_zh(text):
                return text

    return ""


INVESTIGATORS: dict[str, dict] = {
    "roland_banks": {
        "name": "Roland Banks",
        "name_cn": "罗兰·班克斯",
        "class": PlayerClass.GUARDIAN,
        "health": 9,
        "sanity": 5,
        "skills": SkillValues(willpower=3, intellect=3, combat=4, agility=2),
        "ability_cn": "你在击败敌人后可发现1条线索（简化：不自动实现）。",
    },
    "daisy_walker": {
        "name": "Daisy Walker",
        "name_cn": "黛西·沃克",
        "class": PlayerClass.SEEKER,
        "health": 5,
        "sanity": 9,
        "skills": SkillValues(willpower=3, intellect=5, combat=2, agility=2),
        "ability_cn": "每回合+1行动（仅典籍）。",
    },
    "skids_otoole": {
        "name": "Skids O'Toole",
        "name_cn": "斯基兹·奥图尔",
        "class": PlayerClass.ROGUE,
        "health": 8,
        "sanity": 6,
        "skills": SkillValues(willpower=2, intellect=3, combat=3, agility=4),
        "ability_cn": "你可以花费2资源获得+1行动（简化：不自动实现）。",
    },
    "agnes_baker": {
        "name": "Agnes Baker",
        "name_cn": "艾格尼丝·贝克",
        "class": PlayerClass.MYSTIC,
        "health": 6,
        "sanity": 8,
        "skills": SkillValues(willpower=5, intellect=2, combat=2, agility=3),
        "ability_cn": "你受到恐惧后可对敌人造成1伤害（简化：不自动实现）。",
    },
    "wendy_adams": {
        "name": "Wendy Adams",
        "name_cn": "温蒂·亚当斯",
        "class": PlayerClass.SURVIVOR,
        "health": 7,
        "sanity": 7,
        "skills": SkillValues(willpower=4, intellect=3, combat=1, agility=4),
        "ability_cn": "弃1张牌重抽混沌标记（简化：不自动实现）。",
    },
}


DECK_PRESETS: dict[str, dict] = {
    "roland_starter": {
        "name_cn": "罗兰·班克斯（入门战斗）",
        "investigator_id": "roland_banks",
        "cards": [
            "machete_lv0",
            "45_automatic_lv0",
            "flashlight_lv0",
            "emergency_cache_lv0",
            "beat_cop_lv0",
            "guard_dog_lv0",
            "first_aid_lv0",
            "dodge_lv0",
            "evidence_lv0",
            "vicious_blow_lv0",
            "guts_lv0",
            "overpower_lv0",
            "perception_lv0",
            "manual_dexterity_lv0",
            "unexpected_courage_lv0",
        ],
    },
    "daisy_starter": {
        "name_cn": "黛西·沃克（入门调查）",
        "investigator_id": "daisy_walker",
        "cards": [
            "magnifying_glass_lv0",
            "old_book_of_lore_lv0",
            "medical_texts_lv0",
            "dr_milan_christopher_lv0",
            "research_librarian_lv0",
            "working_a_hunch_lv0",
            "deduction_lv0",
            "perception_lv0",
            "guts_lv0",
            "unexpected_courage_lv0",
            "preposterous_sketches_lv0",
            "inquiring_mind_lv0",
            "mind_over_matter_lv0",
            "shortcut_lv0",
            "knife_lv0",
        ],
    },
    "skids_starter": {
        "name_cn": "斯基兹·奥图尔（入门机动）",
        "investigator_id": "skids_otoole",
        "cards": [
            "switchblade_lv0",
            "forty_one_derringer_lv0",
            "burglary_lv0",
            "pickpocketing_lv0",
            "sneak_attack_lv0",
            "elusive_lv0",
            "opportunist_lv0",
            "hard_knocks_lv0",
            "leo_de_luca_lv0",
            "emergency_cache_lv0",
            "manual_dexterity_lv0",
            "overpower_lv0",
            "perception_lv0",
            "unexpected_courage_lv0",
            "knife_lv0",
        ],
    },
    "agnes_starter": {
        "name_cn": "艾格尼丝·贝克（入门法术）",
        "investigator_id": "agnes_baker",
        "cards": [
            "shrivelling_lv0",
            "holy_rosary_lv0",
            "arcane_studies_lv0",
            "ward_of_protection_lv0",
            "forbidden_knowledge_lv0",
            "drawn_to_the_flame_lv0",
            "fearless_lv0",
            "blinding_light_lv0",
            "guts_lv0",
            "unexpected_courage_lv0",
            "emergency_cache_lv0",
            "perception_lv0",
            "manual_dexterity_lv0",
            "knife_lv0",
            "flashlight_lv0",
        ],
    },
    "wendy_starter": {
        "name_cn": "温蒂·亚当斯（入门生存）",
        "investigator_id": "wendy_adams",
        "cards": [
            "baseball_bat_lv0",
            "rabbits_foot_lv0",
            "leather_coat_lv0",
            "lucky_lv0",
            "look_what_i_found_lv0",
            "stray_cat_lv0",
            "scavenging_lv0",
            "survival_instinct_lv0",
            "dig_deep_lv0",
            "manual_dexterity_lv0",
            "guts_lv0",
            "overpower_lv0",
            "perception_lv0",
            "unexpected_courage_lv0",
            "emergency_cache_lv0",
        ],
    },
}


def _load_player_cards(g: Game) -> None:
    """Load `data/player_cards/**/*.json` into `card_database` (CardData)."""
    import json

    def to_player_class(v: str) -> PlayerClass:
        return PlayerClass(v)

    def to_card_type(v: str) -> CardType:
        return CardType(v)

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

        # Capture deckbuilding metadata (signature/weakness/deck limit)
        meta = {
            "signature": (data.get("signature") or "").strip(),
            "weakness": bool(data.get("weakness") or False),
            "placeholder": bool(data.get("placeholder") or False),
            "subtype": (data.get("subtype") or "").strip(),
        }
        dl = data.get("deck_limit")
        try:
            meta["deck_limit"] = int(dl) if dl is not None else (1 if (meta["weakness"] or meta["signature"] or meta["placeholder"]) else 2)
        except Exception:
            meta["deck_limit"] = 1 if (meta["weakness"] or meta["signature"] or meta["placeholder"]) else 2
        _CARD_META[card_id] = meta
        # Chinese text source priority:
        # 1) JSON `text_cn` (explicit)
        # 2) `all_cards.json` (ArkhamDB CN export, preferred)
        # 3) JSON `text` only if it itself is Chinese
        text_cn = (data.get("text_cn") or "").strip()
        if not _has_zh(text_cn):
            text_cn = _lookup_text_cn_from_all_cards(
                name_en=(data.get("name") or ""),
                type_code=(data.get("type") or ""),
                faction_code=(data.get("class") or "neutral"),
                level=int(data.get("level") or 0),
            )
        if not _has_zh(text_cn):
            maybe = (data.get("text") or "").strip()
            if _has_zh(maybe):
                text_cn = maybe

        try:
            cd = CardData(
                id=card_id,
                name=data.get("name") or card_id,
                name_cn=data.get("name_cn") or "",
                type=to_card_type(data.get("type")),
                card_class=to_player_class(data.get("class") or "neutral"),
                cost=data.get("cost"),
                level=int(data.get("level") or 0),
                traits=list(data.get("traits") or []),
                skill_icons=dict(data.get("skill_icons") or {}),
                slots=to_slots(list(data.get("slots") or [])),
                # Frontend requirement: never display English card text.
                # Use CN from `all_cards.json` when JSON lacks `text_cn`.
                text=text_cn,
                health=data.get("health"),
                sanity=data.get("sanity"),
                        pack=data.get("pack") or "",
                        unique=bool(data.get("unique") or False),
                        fast=bool(data.get("fast") or False),
                    )
        except Exception:
            # Skip malformed cards
            continue

        g.register_card_data(cd)


def _load_player_card_catalog() -> list[dict]:
    """Load all player card JSON definitions for deck builder UI.

    IMPORTANT: Only return Chinese fields for display (no EN fallback).
    """
    global _PLAYER_CARD_CATALOG_CACHE
    if _PLAYER_CARD_CATALOG_CACHE is not None:
        return _PLAYER_CARD_CATALOG_CACHE

    import json as _json

    def to_slots(values: list[str]) -> list[str]:
        out: list[str] = []
        for s in values or []:
            if s.endswith("_x2"):
                base = s[:-3]
                out.extend([base, base])
            elif s == "hand_x2":
                out.extend(["hand", "hand"])
            elif s == "arcane_x2":
                out.extend(["arcane", "arcane"])
            else:
                out.append(s)
        return out

    base = PROJECT_ROOT / "data" / "player_cards"
    cards: list[dict] = []
    for p in base.rglob("*.json"):
        if p.name == "schema.json":
            continue
        try:
            data = _json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue

        cid = data.get("id")
        if not cid:
            continue

        # Deckbuilding metadata for UI
        signature = (data.get("signature") or "").strip()
        weakness = bool(data.get("weakness") or False)
        placeholder = bool(data.get("placeholder") or False)
        subtype = (data.get("subtype") or "").strip()
        dl = data.get("deck_limit")
        try:
            deck_limit = int(dl) if dl is not None else (1 if (weakness or signature or placeholder) else 2)
        except Exception:
            deck_limit = 1 if (weakness or signature or placeholder) else 2

        deck_role = "placeholder" if placeholder else ("weakness" if weakness else ("signature" if signature else "normal"))

        cards.append(
            {
                "id": cid,
                "name_cn": data.get("name_cn") or "",
                "type": data.get("type") or "",
                "class": data.get("class") or "neutral",
                "cost": data.get("cost"),
                "level": int(data.get("level") or 0),
                "traits": list(data.get("traits") or []),
                "slots": to_slots(list(data.get("slots") or [])),
                # CN-only text for tooltip/details
                "text_cn": (
                    (data.get("text_cn") or "").strip()
                    or _lookup_text_cn_from_all_cards(
                        name_en=(data.get("name") or ""),
                        type_code=(data.get("type") or ""),
                        faction_code=(data.get("class") or "neutral"),
                        level=int(data.get("level") or 0),
                    )
                ),
                "skill_icons": dict(data.get("skill_icons") or {}),

                # Extra metadata (for deckbuilding rules/counting)
                "deck_role": deck_role,
                "deck_limit": deck_limit,
                "signature": signature,
                "weakness": weakness,
                "subtype": subtype,
                "placeholder": placeholder,
            }
        )

    # Stable sort: class -> cost -> level -> id
    def sort_key(c: dict):
        cost = c.get("cost")
        cost_val = cost if isinstance(cost, int) else 999
        return (str(c.get("class") or ""), cost_val, int(c.get("level") or 0), str(c.get("id") or ""))

    cards.sort(key=sort_key)
    _PLAYER_CARD_CATALOG_CACHE = cards
    return cards


def _parse_deck_text(text: str) -> list[str]:
    """Parse a deck list text into a list of card_ids.

    Supported:
    - `2 machete_lv0`
    - `machete_lv0 x2` / `machete_lv0 *2`
    - `machete_lv0` per line
    """
    import re

    out: list[str] = []
    # Arkham deckbuilding baseline: usually max 2 copies per card.
    counts: dict[str, int] = {}
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue

        line = re.sub(r"\s+", " ", line)
        m = re.match(r"^(\d+)\s+([a-z0-9_]+)$", line)
        if m:
            n = int(m.group(1))
            cid = m.group(2)
            counts[cid] = counts.get(cid, 0) + n
            continue
        m = re.match(r"^([a-z0-9_]+)\s*[x\*]\s*(\d+)$", line, flags=re.I)
        if m:
            cid = m.group(1)
            n = int(m.group(2))
            counts[cid] = counts.get(cid, 0) + n
            continue

        # fallback: take first token as card_id
        cid = line.split(" ", 1)[0]
        if re.match(r"^[a-z0-9_]+$", cid):
            counts[cid] = counts.get(cid, 0) + 1

    # Enforce per-card cap (deck_limit; default 2, weakness/signature default 1)
    for cid, n in counts.items():
        try:
            limit = int((_card_meta(cid).get("deck_limit") or 0) or 0)
        except Exception:
            limit = 0
        if limit <= 0:
            limit = 1 if _deck_role(cid) in {"signature", "weakness", "placeholder"} else 2
        out.extend([cid] * min(limit, n))
    return out


def _validate_and_build_deck(
    g: Game,
    *,
    investigator_id: str,
    chosen_ids: list[str],
    strict: bool,
) -> tuple[list[str], list[str]]:
    """Validate deckbuilding rules and return (main_30, extras).

    - main deck: counts toward size (usually 30)
    - extras: signature/weakness cards that do not count
    """
    profile = _load_investigator_profile(investigator_id)
    req = dict(profile.get("deck_requirements") or {})
    size = int(req.get("size") or 30)
    allowed: dict = dict(req.get("cards") or {})

    # Split roles
    main: list[str] = []
    picked_special: list[str] = []
    for cid in chosen_ids:
        role = _deck_role(cid)
        if role == "normal":
            main.append(cid)
        elif role != "placeholder":
            picked_special.append(cid)

    # Deck size check (only for main)
    if len(main) != size:
        if strict:
            raise ValueError(f"卡组张数不正确：主卡组需要{size}张（不含专属卡/弱点），当前为{len(main)}张")

    # Investigator-specific allowed cards check (only when we have a profile)
    errors: list[str] = []
    if allowed:
        for cid in main:
            cd = g.state.get_card_data(cid)
            if cd is None:
                errors.append(f"未知卡牌：{cid}")
                continue
            cls = (cd.card_class.value if cd.card_class else "neutral")
            lvl = int(getattr(cd, "level", 0) or 0)
            rule = allowed.get(cls)
            if not rule:
                errors.append(f"不符合构筑：{cd.name_cn or cd.name}（{cid}）不允许放入该调查员卡组")
                continue
            mn = int(rule.get("min_level") or 0)
            mx = int(rule.get("max_level") or 0)
            if lvl < mn or lvl > mx:
                errors.append(
                    f"不符合构筑：{cd.name_cn or cd.name}（{cid}）等级{lvl}不在允许范围{mn}-{mx}"
                )

    if errors and strict:
        raise ValueError("；".join(errors))

    # Required signatures / weaknesses (auto append)
    sigs: list[str] = list(profile.get("signature_cards") or [])
    inv_weakness = (profile.get("weakness") or "").strip()
    # Deduplicate weakness from signatures list if present
    sigs = [c for c in sigs if c and c != inv_weakness]

    # Basic weakness selection (allow at most 1 non-placeholder weakness that is not investigator signature)
    basic_weaknesses: list[str] = []
    for cid in picked_special:
        m = _card_meta(cid)
        if not m.get("weakness"):
            continue
        if m.get("placeholder"):
            continue
        if (m.get("signature") or "").strip():
            # Investigator signature weakness handled separately
            continue
        basic_weaknesses.append(cid)

    # If user selected multiple basic weaknesses, reject in strict mode
    if strict and len(basic_weaknesses) > 1:
        raise ValueError(f"基礎弱點只能选择1张：当前选择了{len(basic_weaknesses)}张")

    extras: list[str] = []
    for cid in (sigs + ([inv_weakness] if inv_weakness else []) + basic_weaknesses[:1]):
        if not cid:
            continue
        if g.state.get_card_data(cid) is None:
            if strict:
                raise ValueError(f"缺少必需的专属卡/弱点：{cid}")
            continue
        if cid not in extras:
            extras.append(cid)

    # Enforce deck limits globally
    counts: dict[str, int] = {}
    for cid in list(main) + list(extras):
        counts[cid] = counts.get(cid, 0) + 1
    for cid, n in counts.items():
        try:
            limit = int((_card_meta(cid).get("deck_limit") or 0) or 0)
        except Exception:
            limit = 0
        if limit <= 0:
            limit = 1 if _deck_role(cid) in {"signature", "weakness", "placeholder"} else 2
        if n > limit and strict:
            cd = g.state.get_card_data(cid)
            nm = (cd.name_cn or cd.name) if cd else cid
            raise ValueError(f"超过牌组上限：{nm}（{cid}）最多{limit}张，当前{n}张")

    return (main, extras)


def _clear_game_over_if_needed():
    global game_over
    if game is None:
        return
    res = game.state.scenario.vars.get("resolution_id")
    if res and not game_over:
        # Very simple mapping: R1/R2 treated as win-ish, others lose.
        win = res in {"R1", "R2"}
        msg = game.state.scenario.vars.get("resolution_message") or f"结局：{res}"
        game_over = {"type": "win" if win else "lose", "message": msg}


def create_game(
    *,
    scenario_id: str = "the_gathering",
    investigator_id: str = "daisy_walker",
    deck_preset: str = "",
    deck_text: str = "",
) -> Game:
    """Initialize a 1-investigator playable game for a core scenario."""
    global action_log, game_over, controller
    action_log = []
    game_over = None

    g = Game(scenario_id)
    g.chaos_bag.seed(42)

    # Load all player cards (105 cards) from JSON
    _load_player_cards(g)

    # Filler for padding
    filler = CardData(
        id="filler",
        name="Filler Card",
        name_cn="填充卡",
        type=CardType.SKILL,
        card_class=PlayerClass.NEUTRAL,
        cost=None,
        skill_icons={"wild": 1},
        text="占位符。",
    )
    g.register_card_data(filler)

    # Investigator selection
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

    # Build deck from preset or text
    deck_ids: list[str] = []
    if deck_text.strip():
        deck_ids = _parse_deck_text(deck_text)
    elif deck_preset and deck_preset in DECK_PRESETS:
        base = list(DECK_PRESETS[deck_preset]["cards"])
        # Default 2 copies each
        deck_ids = []
        for cid in base:
            deck_ids.extend([cid, cid])
    else:
        # Fallback to investigator matching preset
        for preset_id, preset in DECK_PRESETS.items():
            if preset.get("investigator_id") == investigator_id:
                for cid in preset["cards"]:
                    deck_ids.extend([cid, cid])
                break

    # Validate card ids; drop unknowns
    deck_ids = [cid for cid in deck_ids if g.state.get_card_data(cid) is not None]

    # Deckbuilding rules:
    # - main deck size is usually 30
    # - signature/weakness cards do NOT count toward 30, and are auto-added
    profile = _load_investigator_profile(investigator_id)
    size = int((profile.get("deck_requirements") or {}).get("size") or 30)
    # Only enforce strict deckbuilding for investigators that have explicit deck rules defined.
    # (Currently: Daisy Walker). Others keep legacy behavior (pad/truncate with filler).
    strict = bool(profile.get("deck_requirements")) and bool(deck_text.strip() or (deck_preset and deck_preset in DECK_PRESETS))

    try:
        main_deck, extras = _validate_and_build_deck(g, investigator_id=investigator_id, chosen_ids=deck_ids, strict=strict)
    except ValueError:
        if strict:
            raise
        # fallback: allow quick-start with fillers
        main_deck, extras = (list(deck_ids), [])

    if not main_deck:
        main_deck = ["filler"] * size

    if len(main_deck) < size:
        if strict:
            raise ValueError(f"卡组张数不足：主卡组需要{size}张（不含专属卡/弱点），当前为{len(main_deck)}张")
        main_deck += ["filler"] * (size - len(main_deck))
    elif len(main_deck) > size:
        if strict:
            raise ValueError(f"卡组张数超出：主卡组需要{size}张（不含专属卡/弱点），当前为{len(main_deck)}张")
        main_deck = main_deck[:size]

    deck_ids = list(main_deck) + list(extras)
    random.shuffle(deck_ids)

    # Apply scenario data (locations, act/agenda, encounter deck)
    apply_scenario_to_game(g, scenario_id, seed=42)

    scen = load_scenario_definition(scenario_id)
    g.add_investigator("player", inv_data, deck=deck_ids, starting_location=scen["start_location"])
    g.setup()

    # Scenario-wide runtime flags
    if scenario_id == "the_midnight_masks":
        g.state.scenario.vars["central_location"] = "downtown"
    else:
        g.state.scenario.vars["central_location"] = scen["start_location"]

    controller = ScenarioController(g, action_log=action_log)
    controller.attach()

    # System loggers (draw/clue/resource/move/combat etc.)
    _attach_system_loggers(g)

    g.state.scenario.current_phase = Phase.INVESTIGATION
    g.state.scenario.round_number = 1
    g.state.scenario.vars["_action_seq"] = 0
    action_log.append(f"=== 核心剧本：{scen.get('name_cn', scenario_id)} ===")
    action_log.append(f"调查员：{inv_data.name_cn}")
    action_log.append("第1轮 调查阶段")

    return g


def serialize_state(g: Game) -> dict:
    """Serialize game state using the shared serializer."""
    _clear_game_over_if_needed()
    return _serialize_game_state(
        g,
        action_log=action_log,
        game_over=game_over,
        viewer_investigator_id="player",
    )


def handle_action(data: dict) -> dict:
    global game, game_over
    if game is None:
        return {"success": False, "message": "游戏未初始化"}
    inv = game.state.get_investigator("player")
    if inv is None:
        return {"success": False, "message": "未找到调查员"}
    if game_over or inv.is_defeated:
        return {"success": False, "message": "游戏已结束"}

    act = data.get("action")
    if not act:
        return {"success": False, "message": "缺少 action"}

    # Resolve pending choice
    if act == "RESOLVE_CHOICE":
        pc = game.state.scenario.vars.get("pending_choice")
        if not pc:
            return {"success": False, "message": "当前没有待选择项"}
        choice_id = data.get("choice_id")

        kind = pc.get("kind") or "encounter"

        # Clear pending choice now (handlers can re-add if needed)
        game.state.scenario.vars.pop("pending_choice", None)

        if kind == "encounter":
            card_id = pc.get("card_id")
            controller.resolve_encounter_card(card_id, choice=choice_id)
            _clear_game_over_if_needed()
            return {"success": True, "message": "已选择"}

        if kind == "asset_old_book_of_lore":
            peek_cards: list[str] = list(pc.get("peek_cards") or [])
            if not peek_cards:
                return {"success": False, "message": "智慧古书：没有可选卡牌"}

            chosen = choice_id if choice_id in peek_cards else peek_cards[0]
            rest = [c for c in peek_cards if c != chosen]

            # Draw chosen; put rest to bottom (keep original order)
            inv.hand.append(chosen)
            inv.deck.extend(rest)

            cd = game.state.get_card_data(chosen)
            chosen_name = (cd.name_cn or "").strip() if cd else ""
            if not chosen_name:
                chosen_name = "（未翻译卡牌）"

            action_log.append(f"📚 智慧古书：你选择抽取【{chosen_name}】（其余{len(rest)}张置于牌库底）")
            return {"success": True, "message": "已抽牌"}

        return {"success": False, "message": f"未知选择类型：{kind}"}

    # Scenario actions
    if act == "ADVANCE_ACT":
        if inv.actions_remaining <= 0:
            return {"success": False, "message": "没有行动点"}
        if controller.advance_act("player"):
            inv.actions_remaining -= 1
            _clear_game_over_if_needed()
            return {"success": True, "message": "事件推进"}
        return {"success": False, "message": "不满足推进条件（线索不足或无事件）"}

    if act == "RESIGN":
        rid = controller.resign()
        _clear_game_over_if_needed()
        return {"success": True, "message": f"撤退结局：{rid}"}

    if act == "LOCKED_DOOR_TEST":
        # action: test combat/agility (4) to discard locked door
        if inv.actions_remaining <= 0:
            return {"success": False, "message": "没有行动点"}
        skill = data.get("skill")
        if skill not in {"combat", "agility"}:
            return {"success": False, "message": "skill 必须是 combat/agility"}
        attached = game.state.scenario.vars.get("treacheries", {}).get("locked_door", {}).get("attached_to")
        if not attached:
            return {"success": False, "message": "当前没有上锁的门"}

        from backend.models.enums import Skill

        inv.actions_remaining -= 1
        ok = {"success": False}

        def on_success(_r):
            ok["success"] = True
            controller.remove_treachery("locked_door")
            action_log.append("🚪 你打开了上锁的门（Locked Door弃掉）")

        game.skill_test_engine.run_test(
            investigator_id="player",
            skill_type=Skill.COMBAT if skill == "combat" else Skill.AGILITY,
            difficulty=4,
            committed_card_ids=data.get("committed_cards", []) or [],
            on_success=on_success,
            on_failure=lambda _r: None,
        )
        return {"success": ok["success"], "message": "开锁成功" if ok["success"] else "开锁失败"}

    # Activate an asset in play (used by Old Book of Lore, etc.)
    if act == "ACTIVATE_ASSET":
        if inv.actions_remaining <= 0:
            return {"success": False, "message": "没有行动点"}
        instance_id = data.get("instance_id")
        if not instance_id:
            return {"success": False, "message": "缺少 instance_id"}
        if instance_id not in inv.play_area:
            return {"success": False, "message": "该支援不在你的装备区"}
        ci = game.state.get_card_instance(instance_id)
        if not ci:
            return {"success": False, "message": "未找到支援实例"}
        if ci.exhausted:
            return {"success": False, "message": "该支援已消耗"}

        card_id = ci.card_id
        # Only implement what is needed now
        if card_id == "old_book_of_lore_lv0":
            if not inv.deck:
                return {"success": False, "message": "牌库为空，无法使用智慧古书"}

            # Pay cost: 1 action + exhaust
            inv.actions_remaining -= 1
            ci.exhausted = True

            peek_n = min(3, len(inv.deck))
            peek_cards: list[str] = []
            for _ in range(peek_n):
                peek_cards.append(inv.deck.pop(0))

            def label(cid: str) -> str:
                cd = game.state.get_card_data(cid)
                nm = (cd.name_cn or "").strip() if cd else ""
                if not nm:
                    nm = "（未翻译卡牌）"
                return f"{nm}"

            options = [{"id": cid, "label": label(cid)} for cid in peek_cards]
            game.state.scenario.vars["pending_choice"] = {
                "kind": "asset_old_book_of_lore",
                "card_id": card_id,
                "asset_instance_id": instance_id,
                "peek_cards": peek_cards,
                "prompt": "<b>智慧古书</b>：查看牌库顶3张牌，选择1张加入手牌（其余置于牌库底）。",
                "options": options,
            }
            action_log.append("📚 智慧古书：查看牌库顶3张，等待选择…")
            return {"success": True, "message": "需要做出选择"}

        return {"success": False, "message": "该支援暂不支持激活"}

    # Normal actions (INVESTIGATE/MOVE/FIGHT/EVADE/DRAW/RESOURCE/PLAY/ENGAGE)
    action_name = act
    try:
        enum_act = Action[action_name]
    except Exception:
        return {"success": False, "message": f"未知 action: {action_name}"}

    # Disallow play under Dissonant Voices
    if enum_act == Action.PLAY and controller.has_treachery("dissonant_voices"):
        return {"success": False, "message": "不和谐的低语：本轮不能打出支援/事件"}

    # Frozen in Fear: first move/fight/evade costs +1 action
    if enum_act in {Action.MOVE, Action.FIGHT, Action.EVADE} and controller.has_treachery("frozen_in_fear"):
        if not game.state.scenario.vars.get("frozen_in_fear_used", False):
            if inv.actions_remaining <= 1:
                return {"success": False, "message": "恐惧冻结：需要额外1行动"}
            inv.actions_remaining -= 1
            game.state.scenario.vars["frozen_in_fear_used"] = True
            action_log.append("🥶 恐惧冻结：支付额外1行动")

    # Locked Door prevents investigate at attached location
    if enum_act == Action.INVESTIGATE:
        attached = game.state.scenario.vars.get("treacheries", {}).get("locked_door", {}).get("attached_to")
        if attached and attached == inv.location_id:
            return {"success": False, "message": "上锁的门：该地点无法调查"}

    # Obscuring Fog +2 shroud
    fog_loc = game.state.scenario.vars.get("treacheries", {}).get("obscuring_fog", {}).get("attached_to")
    shroud_bump = False
    if enum_act == Action.INVESTIGATE and fog_loc == inv.location_id:
        loc = game.state.get_location(inv.location_id)
        if loc:
            loc.card_data.shroud = (loc.card_data.shroud or 0) + 2
            shroud_bump = True

    # For better UX/debug: record deltas for PLAY
    played_card_id = data.get("card_id") if enum_act == Action.PLAY else None
    before_hand = len(inv.hand)
    before_deck = len(inv.deck)
    before_discard = len(inv.discard)

    try:
        ok = game.action_resolver.perform_action("player", enum_act, **{k: v for k, v in data.items() if k != "action"})
    finally:
        if shroud_bump:
            loc = game.state.get_location(inv.location_id)
            if loc:
                loc.card_data.shroud = max(0, (loc.card_data.shroud or 0) - 2)

    if not ok:
        return {"success": False, "message": "行动失败"}

    # Action succeeded: add helpful log for played cards (esp. draw effects)
    if played_card_id:
        cd = game.state.get_card_data(played_card_id)
        name_cn = (cd.name_cn or "").strip() if cd else ""
        if not name_cn:
            name_cn = "（未翻译卡牌）"
        delta_hand = len(inv.hand) - before_hand
        delta_deck = len(inv.deck) - before_deck
        delta_discard = len(inv.discard) - before_discard
        action_log.append(f"🃏 打出：{name_cn}（手牌{delta_hand:+d}，牌库{delta_deck:+d}，弃牌{delta_discard:+d}）")

    return {"success": True, "message": "行动成功"}


def handle_end_turn() -> dict:
    global game, game_over
    if game is None:
        return {"success": False, "message": "游戏未初始化"}
    inv = game.state.get_investigator("player")
    if inv is None:
        return {"success": False, "message": "未找到调查员"}
    if inv.is_defeated or game_over:
        return {"success": False, "message": "游戏已结束"}

    # End of your turn: Frozen in Fear test
    if controller.has_treachery("frozen_in_fear"):
        from backend.models.enums import Skill

        ok = {"success": False}

        def on_success(_r):
            ok["success"] = True
            controller.remove_treachery("frozen_in_fear")
            action_log.append("🥶 恐惧冻结：意志检定成功，弃掉")

        game.skill_test_engine.run_test(
            investigator_id="player",
            skill_type=Skill.WILLPOWER,
            difficulty=3,
            committed_card_ids=[],
            on_success=on_success,
            on_failure=lambda _r: None,
        )

    # Enemy Phase
    action_log.append("--- 敌人阶段 ---")
    old_d = inv.damage
    old_h = inv.horror
    game.enemy_phase.resolve()
    if inv.damage > old_d or inv.horror > old_h:
        action_log.append(f"👹 敌人攻击：{inv.damage-old_d}伤害/{inv.horror-old_h}恐惧")

    if inv.is_defeated:
        game_over = {"type": "lose", "message": "调查员被击败！"}
        return {"success": True, "message": game_over["message"]}

    # Upkeep Phase
    action_log.append("--- 刷新阶段 ---")
    game.upkeep_phase.resolve()
    action_log.append("♻️ 就绪、抽1牌、+1资源")

    # End of round: Dissonant Voices discards
    if controller.has_treachery("dissonant_voices"):
        controller.remove_treachery("dissonant_voices")
        action_log.append("🔇 不和谐的低语：回合结束弃掉")

    # New Round
    game.state.scenario.round_number += 1
    game.state.scenario.vars["frozen_in_fear_used"] = False
    game.state.scenario.vars["_action_seq"] = 0

    # Mythos Phase
    action_log.append("--- 神话阶段 ---")
    game.state.scenario.doom_on_agenda += 1
    controller._check_agenda_threshold()  # type: ignore[attr-defined]
    _clear_game_over_if_needed()
    if game_over:
        return {"success": True, "message": game_over["message"]}

    # Encounter draw
    scen = game.state.scenario
    if not scen.encounter_deck:
        scen.encounter_deck = list(scen.encounter_discard)
        random.shuffle(scen.encounter_deck)
        scen.encounter_discard.clear()
        action_log.append("♻️ 遭遇弃牌堆洗回")

    if scen.encounter_deck:
        enc_id = scen.encounter_deck.pop(0)
        scen.encounter_discard.append(enc_id)
        res = controller.resolve_encounter_card(enc_id)
        if res.get("surge"):
            # draw one more
            if scen.encounter_deck:
                enc2 = scen.encounter_deck.pop(0)
                scen.encounter_discard.append(enc2)
                controller.resolve_encounter_card(enc2)
        if res.get("pending"):
            return {"success": True, "message": "需要做出选择"}

    if inv.is_defeated:
        game_over = {"type": "lose", "message": "调查员被遭遇击败！"}
        return {"success": True, "message": game_over["message"]}

    _clear_game_over_if_needed()
    if game_over:
        return {"success": True, "message": game_over["message"]}

    # Begin new investigation
    inv.actions_remaining = 3
    game.state.scenario.current_phase = Phase.INVESTIGATION
    action_log.append(f"=== 第{game.state.scenario.round_number}轮 调查阶段 ===")
    return {"success": True, "message": "进入下一轮"}


class GameHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/":
            self._serve_html()
        elif path == "/api/state":
            self._json_response(serialize_state(game))
        elif path == "/api/player-cards":
            self._json_response({"cards": _load_player_card_catalog()})
        elif path == "/api/deck-presets":
            self._json_response(
                {
                    "presets": {
                        pid: {
                            "id": pid,
                            "name_cn": preset.get("name_cn") or pid,
                            "investigator_id": preset.get("investigator_id") or "",
                            "cards": list(preset.get("cards") or []),
                            "default_copies": 2,
                        }
                        for pid, preset in DECK_PRESETS.items()
                    }
                }
            )
        else:
            self.send_error(404)

    def do_POST(self):
        global game
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length else b"{}"
        data = json.loads(body) if body else {}

        if self.path == "/api/setup":
            scenario_id = data.get("scenario_id") or "the_gathering"
            investigator_id = data.get("investigator_id") or "daisy_walker"
            deck_preset = data.get("deck_preset") or ""
            deck_text = data.get("deck_text") or ""
            try:
                game = create_game(
                    scenario_id=scenario_id,
                    investigator_id=investigator_id,
                    deck_preset=deck_preset,
                    deck_text=deck_text,
                )
            except ValueError as e:
                self._json_response({"success": False, "message": str(e), "state": serialize_state(game) if game else None})
                return
            self._json_response({"success": True, "message": "游戏已初始化", "state": serialize_state(game)})
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
        html_path = Path(__file__).parent / "scenario.html"
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html_path.read_bytes())

    def log_message(self, format, *args):
        pass


def main():
    global game
    game = create_game(scenario_id="the_gathering")
    port = 8910
    server = HTTPServer(("0.0.0.0", port), GameHandler)
    print("Arkham Horror LCG — Core Campaign Server")
    print(f"http://localhost:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")


if __name__ == "__main__":
    main()
