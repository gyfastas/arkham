"""遗忘时代 (The Forgotten Age) 8 章符号 token 效果。

官方文本来源：data/encounter_cards/the_forgotten_age.json 中 type=scenario 的
剧本参考卡（text=简单/普通面，back_text=困难/专家面，以英文为准）。
结构化参考：.tools/arkham-cards-data/chaos_tokens.json。

接线约定（本模块不自行订阅事件）：
- official_core 的符号 token 分发器调用 ``apply_token``；返回 True 表示已命中处理，
  中文提示写入 ``ctx.extra["token_text"]``（与 dunwich/carcosa 分支一致，由分发器统一记日志）。
- SKILL_TEST_FAILED / SKILL_TEST_SUCCESSFUL 时由分发器调用 ``on_fail`` / ``on_success``，
  传入对应调查员的 pending 集合；已结算的 key 会从集合中移除（幂等）。

TFA 特有概念（引擎未实装，统一以 scenario.vars 记录，由剧本逻辑维护）：
- 复仇点：``vars["vengeance"]``（int，胜利区复仇点总数）。
- 探索牌堆：``vars["exploration_deck"]``（card_id 列表，数量即 len()）。
- 中毒：``vars["poisoned"]``（investigator_id 列表）；官方"将搁置的 Poisoned
  弱点置入威胁区"简化为加入该列表。
- 约顿深渊深度：``vars["depth_level"]``（int）。

简化项（与官方规则的差异，玩家选择分支自动取最常用/最有利者）：
- "选择 1 个异教徒敌人放毁灭"等玩家自选目标 → 自动选最近的（交战 > 同地点 > 任意）。
- 直接伤害（direct damage）按普通伤害结算（未实装不可分配语义）。
- "洗入探索牌堆"简化为 append 到 vars["exploration_deck"]（不真正洗牌）。
- 古代遗物（Relic of Ages）位置：视为随身携带（在持有者支援区）或附着在地点
  （attached_to == 地点），也可用 vars["relic_location"] 显式指定。
"""

from __future__ import annotations

TFA_SCENARIO_IDS = {
    "wilds",
    "eztli",
    "threads_of_fate",
    "the_boundary_beyond",
    "heart_of_the_elders",
    "the_city_of_archives",
    "the_depths_of_yoth",
    "shattered_aeons",
}

# 成功结算时需要"未以至少 N 点优势成功"判定的 pending key
_SUCCESS_MARGIN_KEYS = {
    "tof_cultist_damage": 1,
    "tof_cultist_direct_hard": 2,
    "tof_tablet_doom_nearest": 1,
    "tof_tablet_doom_each_hard": 2,
    "sa_cultist_doom_nearest": 1,
    "sa_cultist_doom_each_hard": 1,
}


# ---------------------
# TFA 概念 helpers（vars 记录）
# ---------------------
def _vengeance(controller) -> int:
    return int(controller.s.vars.get("vengeance", 0) or 0)


def _explore_deck_size(controller) -> int:
    return len(controller.s.vars.get("exploration_deck") or [])


def _is_poisoned(controller, inv_id: str) -> bool:
    return inv_id in (controller.s.vars.get("poisoned") or [])


def _mark_poisoned(controller, inv_id: str) -> None:
    poisoned = controller.s.vars.setdefault("poisoned", [])
    if inv_id not in poisoned:
        poisoned.append(inv_id)


def _depth_level(controller) -> int:
    return int(controller.s.vars.get("depth_level", 0) or 0)


# ---------------------
# 通用 helpers
# ---------------------
def _location_has_trait(controller, location_id: str, *traits: str) -> bool:
    loc = controller.game_state.get_location(location_id)
    if loc is None or loc.card_data is None:
        return False
    have = {str(t).lower() for t in (loc.card_data.traits or [])}
    return any(t.lower() in have for t in traits)


def _enemy_keywords(controller, iid: str) -> list[str]:
    inst = controller.game_state.get_card_instance(iid)
    cd = controller.game_state.get_card_data(inst.card_id) if inst else None
    return list(getattr(cd, "keywords", None) or []) if cd else []


def _enemy_ids_at(controller, location_id: str, keyword: str) -> list[str]:
    """地点的敌人 instance_id（含交战敌人，口径同 controller._enemies_at）。"""
    out: list[str] = []
    loc = controller.game_state.get_location(location_id)
    if loc is not None:
        for iid in loc.enemies:
            if keyword in _enemy_keywords(controller, iid):
                out.append(iid)
    for other in controller.game_state.investigators.values():
        if other.location_id != location_id:
            continue
        for iid in other.threat_area:
            if keyword in _enemy_keywords(controller, iid) and iid not in out:
                out.append(iid)
    return out


def _max_doom_on_cultists(controller) -> int:
    best = 0
    for iid in controller._enemies_with_keyword_in_play("cultist"):
        inst = controller.game_state.get_card_instance(iid)
        if inst is not None:
            best = max(best, getattr(inst, "doom", 0) or 0)
    return best


def _doom_on_locations(controller) -> tuple[int, int]:
    """(有毁灭的地点数, 地点毁灭总数)。"""
    count = 0
    total = 0
    for loc in controller.game_state.locations.values():
        d = getattr(loc, "doom", 0) or 0
        if d:
            count += 1
            total += d
    return count, total


def _nearest_location_with_trait(controller, from_location_id: str, *traits: str) -> str | None:
    best_id = None
    best_d = None
    for lid in controller.game_state.locations:
        if not _location_has_trait(controller, lid, *traits):
            continue
        d = controller._bfs_distance(from_location_id, lid)
        if best_d is None or d < best_d:
            best_id, best_d = lid, d
    return best_id


def _relic_at_investigator_location(controller, inv) -> bool:
    """古代遗物是否在调查员所在地点（简化：随身携带/附着/vars 指定均可）。"""
    loc_id = inv.location_id
    if controller.s.vars.get("relic_location") == loc_id:
        return True
    for iid, inst in controller.game_state.cards_in_play.items():
        if not str(inst.card_id or "").startswith("relic_of_ages"):
            continue
        if getattr(inst, "attached_to", None) == loc_id or iid in inv.play_area:
            return True
    return False


def _shuffle_top_hex_into_explore(controller) -> str | None:
    """遭遇弃牌堆顶（= 列表尾部）最近的 Hex 诡计洗入探索牌堆（简化：append 记录）。"""
    s = controller.s
    discard = s.encounter_discard
    for i in range(len(discard) - 1, -1, -1):
        cid = discard[i]
        cd = controller.game_state.get_card_data(cid)
        if cd is not None and cd.type.value == "treachery" \
                and "hex" in {str(t).lower() for t in (cd.traits or [])}:
            discard.pop(i)
            s.vars.setdefault("exploration_deck", []).append(cid)
            return cid
    return None


def _enemy_attacks(controller, inv, iid: str) -> None:
    inst = controller.game_state.get_card_instance(iid)
    cd = controller.game_state.get_card_data(inst.card_id) if inst else None
    if cd is not None:
        inv.damage += cd.enemy_damage or 0
        inv.horror += cd.enemy_horror or 0


def _doom_nearest_cultist(controller, inv) -> bool:
    target = controller._nearest_enemy_with(inv, "cultist")
    if not target:
        return False
    inst = controller.game_state.get_card_instance(target)
    if inst is None:
        return False
    inst.doom += 1
    return True


def _doom_each_cultist(controller) -> int:
    cultists = controller._enemies_with_keyword_in_play("cultist")
    for iid in cultists:
        inst = controller.game_state.get_card_instance(iid)
        if inst is not None:
            inst.doom += 1
    return len(cultists)


def _move_own_clue_to_location(controller, inv) -> bool:
    if inv.clues <= 0:
        return False
    loc = controller.game_state.get_location(inv.location_id)
    inv.clues -= 1
    if loc is not None:
        loc.clues += 1
    return True


def _add_doom_to_location(controller, inv) -> None:
    loc = controller.game_state.get_location(inv.location_id)
    if loc is not None:
        loc.doom += 1
        controller._check_agenda_threshold()


def _place_clue_on_nearest_ancient(controller, ctx, inv) -> bool:
    lid = _nearest_location_with_trait(controller, inv.location_id, "ancient", "古代")
    if lid is None:
        return False
    loc = controller.game_state.get_location(lid)
    if loc is None:
        return False
    loc.clues += 1
    return True


def _heal_serpents_near(controller, inv) -> int:
    """所在及相连地点的每个巨蛇敌人治疗 2 伤害，返回找到的巨蛇数。"""
    loc = controller.game_state.get_location(inv.location_id)
    loc_ids = [inv.location_id] + list(loc.connections if loc else [])
    found = 0
    seen: set[str] = set()
    for lid in loc_ids:
        for iid in _enemy_ids_at(controller, lid, "serpent"):
            if iid in seen:
                continue
            seen.add(iid)
            inst = controller.game_state.get_card_instance(iid)
            if inst is not None:
                inst.damage = max(0, (inst.damage or 0) - 2)
                found += 1
    return found


# ---------------------
# 符号效果主入口
# ---------------------
def apply_token(controller, ctx, inv, pending, success_pending) -> bool:
    """应用当前剧本（TFA 循环）的符号 token 效果。返回是否命中处理。"""
    from backend.models.enums import ChaosTokenType

    token = ctx.chaos_token
    if token not in (ChaosTokenType.SKULL, ChaosTokenType.CULTIST,
                     ChaosTokenType.TABLET, ChaosTokenType.ELDER_THING):
        return False
    sid = controller.s.scenario_id
    if sid not in TFA_SCENARIO_IDS:
        return False
    hard = controller._is_hard_difficulty

    if sid == "wilds":
        if token == ChaosTokenType.SKULL:
            v = _vengeance(controller)
            x = v + 1 if hard else v
            if x:
                ctx.modify_amount(-x, "wilds_skull")
            ctx.extra["token_text"] = (
                f"骷髅 -{x}（胜利区复仇点{v}{'+1' if hard else ''}）"
            )
        elif token == ChaosTokenType.CULTIST:
            n = len(controller.game_state.locations)
            x = n if hard else min(5, n)
            if x:
                ctx.modify_amount(-x, "wilds_cultist")
            ctx.extra["token_text"] = (
                f"异教徒 -{x}（场上地点数×{n}" + ("）" if hard else "，最大5）")
            )
        elif token == ChaosTokenType.TABLET:
            n = _explore_deck_size(controller)
            x = max(3, n) if hard else min(5, n)
            if x:
                ctx.modify_amount(-x, "wilds_tablet")
            ctx.extra["token_text"] = (
                f"石板 -{x}（探索牌堆{n}张，" + ("最小3）" if hard else "最大5）")
            )
        elif token == ChaosTokenType.ELDER_THING:
            if _is_poisoned(controller, inv.investigator_id):
                ctx.extra["force_auto_fail"] = True
                ctx.extra["token_text"] = "旧神之物 自动失败（已中毒）"
            else:
                v = 3 if hard else 2
                ctx.modify_amount(-v, "wilds_elder_thing")
                if hard:
                    pending.add("wilds_elder_poisoned")
                    ctx.extra["token_text"] = f"旧神之物 -{v}，若失败：中毒（Poisoned 弱点置入威胁区）"
                else:
                    ctx.extra["token_text"] = f"旧神之物 -{v}"

    elif sid == "eztli":
        loc = controller.game_state.get_location(inv.location_id)
        loc_doom = (getattr(loc, "doom", 0) or 0) if loc else 0
        if token == ChaosTokenType.SKULL:
            x = (4 if loc_doom else 2) if hard else (3 if loc_doom else 1)
            ctx.modify_amount(-x, "eztli_skull")
            ctx.extra["token_text"] = f"骷髅 -{x}" + ("（所在地点有毁灭）" if loc_doom else "")
        elif token in (ChaosTokenType.CULTIST, ChaosTokenType.TABLET):
            count, total = _doom_on_locations(controller)
            x = total if hard else count
            if x:
                ctx.modify_amount(-x, f"eztli_{token.value}")
            name = "异教徒" if token == ChaosTokenType.CULTIST else "石板"
            ctx.extra["token_text"] = (
                f"{name} -{x}（" + (f"地点毁灭总数×{x}）" if hard else f"有毁灭的地点数×{x}）")
            )
        elif token == ChaosTokenType.ELDER_THING:
            if hard:
                ctx.extra["token_text"] = "旧神之物 再揭示1个标记，所在地点+1毁灭"
                controller._reveal_extra_numeric_token(ctx, "eztli_elder_extra")
                _add_doom_to_location(controller, inv)
            else:
                pending.add("eztli_elder_doom_loc")
                ctx.extra["token_text"] = "旧神之物 再揭示1个标记，若失败：所在地点+1毁灭"
                controller._reveal_extra_numeric_token(ctx, "eztli_elder_extra")

    elif sid == "threads_of_fate":
        if token == ChaosTokenType.SKULL:
            if hard:
                # 卡面 "total number of doom in play"：含密谋/敌人/地点上的毁灭
                x = controller.game_state.total_doom_in_play()
                note = f"场上毁灭总数×{x}"
            else:
                x = _max_doom_on_cultists(controller)
                note = f"异教徒敌人最高毁灭×{x}"
            if x:
                ctx.modify_amount(-x, "tof_skull")
            ctx.extra["token_text"] = f"骷髅 -{x}（{note}）"
        elif token == ChaosTokenType.CULTIST:
            ctx.modify_amount(-2, "tof_cultist")
            if hard:
                pending.add("tof_cultist_direct_hard")
                success_pending.add("tof_cultist_direct_hard")
                ctx.extra["token_text"] = "异教徒 -2，若未以≥2优势成功：受1直接伤害（简化：按普通伤害）"
            else:
                pending.add("tof_cultist_damage")
                success_pending.add("tof_cultist_damage")
                ctx.extra["token_text"] = "异教徒 -2，若未以≥1优势成功：受1伤害"
        elif token == ChaosTokenType.TABLET:
            ctx.modify_amount(-2, "tof_tablet")
            if hard:
                pending.add("tof_tablet_doom_each_hard")
                success_pending.add("tof_tablet_doom_each_hard")
                ctx.extra["token_text"] = "石板 -2，若未以≥2优势成功：每个异教徒敌人+1毁灭"
            else:
                pending.add("tof_tablet_doom_nearest")
                success_pending.add("tof_tablet_doom_nearest")
                ctx.extra["token_text"] = "石板 -2，若未以≥1优势成功：最近异教徒敌人+1毁灭"
        elif token == ChaosTokenType.ELDER_THING:
            v = 3 if hard else 2
            ctx.modify_amount(-v, "tof_elder_thing")
            pending.add("tof_elder_lose_clue")
            ctx.extra["token_text"] = f"旧神之物 -{v}，若失败：失去1个线索"

    elif sid == "the_boundary_beyond":
        if token == ChaosTokenType.SKULL:
            ancient = _location_has_trait(controller, inv.location_id, "ancient", "古代")
            x = (4 if ancient else 2) if hard else (3 if ancient else 1)
            ctx.modify_amount(-x, "tbb_skull")
            ctx.extra["token_text"] = f"骷髅 -{x}" + ("（古代地点）" if ancient else "")
        elif token == ChaosTokenType.CULTIST:
            if hard:
                pending.add("tbb_cultist_doom_each_hard")
                ctx.extra["token_text"] = "异教徒 再揭示1个标记，若失败：每个异教徒敌人+1毁灭"
            else:
                pending.add("tbb_cultist_doom")
                ctx.extra["token_text"] = "异教徒 再揭示1个标记，若失败：1个异教徒敌人+1毁灭（自动选最近）"
            controller._reveal_extra_numeric_token(ctx, "tbb_cultist_extra")
        elif token == ChaosTokenType.TABLET:
            if hard:
                pending.add("tbb_tablet_serpent_attack_each_hard")
                ctx.extra["token_text"] = "石板 再揭示1个标记，若失败：所在地点每个巨蛇敌人攻击你"
            else:
                pending.add("tbb_tablet_serpent_attack")
                ctx.extra["token_text"] = "石板 再揭示1个标记，若失败且所在地点有巨蛇：它攻击你"
            controller._reveal_extra_numeric_token(ctx, "tbb_tablet_extra")
        elif token == ChaosTokenType.ELDER_THING:
            ctx.modify_amount(-4, "tbb_elder_thing")
            if hard:
                placed = _place_clue_on_nearest_ancient(controller, ctx, inv)
                ctx.extra["token_text"] = "旧神之物 -4，最近的古代地点+1线索" + ("" if placed else "（无古代地点）")
            else:
                pending.add("tbb_elder_clue_ancient")
                ctx.extra["token_text"] = "旧神之物 -4，若失败：最近的古代地点+1线索"

    elif sid == "heart_of_the_elders":
        if token == ChaosTokenType.SKULL:
            cave = _location_has_trait(controller, inv.location_id, "cave", "洞穴")
            x = (4 if cave else 2) if hard else (3 if cave else 1)
            ctx.modify_amount(-x, "hote_skull")
            ctx.extra["token_text"] = f"骷髅 -{x}" + ("（洞穴地点）" if cave else "")
        elif token == ChaosTokenType.CULTIST:
            v = 3 if hard else 2
            ctx.modify_amount(-v, "hote_cultist")
            pending.add("hote_cultist_doom_loc")
            ctx.extra["token_text"] = f"异教徒 -{v}，若失败：所在地点+1毁灭"
        elif token == ChaosTokenType.TABLET:
            if _is_poisoned(controller, inv.investigator_id):
                ctx.extra["force_auto_fail"] = True
                ctx.extra["token_text"] = "石板 自动失败（已中毒）"
            else:
                v = 3 if hard else 2
                ctx.modify_amount(-v, "hote_tablet")
                if hard:
                    pending.add("hote_tablet_poisoned")
                    ctx.extra["token_text"] = f"石板 -{v}，若失败：中毒（Poisoned 弱点置入威胁区）"
                else:
                    ctx.extra["token_text"] = f"石板 -{v}"
        elif token == ChaosTokenType.ELDER_THING:
            v = 4 if hard else 3
            ctx.modify_amount(-v, "hote_elder_thing")
            pending.add("hote_elder_horror")
            ctx.extra["token_text"] = f"旧神之物 -{v}，若失败：受1恐惧"

    elif sid == "the_city_of_archives":
        if token == ChaosTokenType.SKULL:
            big_hand = len(inv.hand) >= 5
            if hard:
                if big_hand:
                    ctx.extra["force_auto_fail"] = True
                    ctx.extra["token_text"] = "骷髅 自动失败（手牌≥5）"
                else:
                    ctx.modify_amount(-2, "tcoa_skull_hard")
                    ctx.extra["token_text"] = "骷髅 -2"
            else:
                x = 3 if big_hand else 1
                ctx.modify_amount(-x, "tcoa_skull")
                ctx.extra["token_text"] = f"骷髅 -{x}" + ("（手牌≥5）" if big_hand else "")
        elif token in (ChaosTokenType.CULTIST, ChaosTokenType.ELDER_THING):
            ctx.modify_amount(-2, f"tcoa_{token.value}")
            name = "异教徒" if token == ChaosTokenType.CULTIST else "旧神之物"
            if hard:
                moved = _move_own_clue_to_location(controller, inv)
                ctx.extra["token_text"] = f"{name} -2，将你的1个线索放到所在地点" + ("" if moved else "（你无线索）")
            else:
                pending.add("tcoa_symbol_clue")
                ctx.extra["token_text"] = f"{name} -2，若失败：将你的1个线索放到所在地点"
        elif token == ChaosTokenType.TABLET:
            ctx.modify_amount(-3, "tcoa_tablet")
            if hard:
                pending.add("tcoa_tablet_discard_margin_hard")
                ctx.extra["token_text"] = "石板 -3，若失败：每低于难度1点随机弃1张手牌"
            else:
                pending.add("tcoa_tablet_discard")
                ctx.extra["token_text"] = "石板 -3，若失败：随机弃1张手牌"

    elif sid == "the_depths_of_yoth":
        if token == ChaosTokenType.SKULL:
            x = _depth_level(controller)
            if x:
                ctx.modify_amount(-x, "tdoy_skull")
            if hard:
                pending.add("tdoy_skull_horror")
                ctx.extra["token_text"] = f"骷髅 -{x}（当前深度），若失败：受1恐惧"
            else:
                ctx.extra["token_text"] = f"骷髅 -{x}（当前深度）"
        elif token == ChaosTokenType.CULTIST:
            pending.add("tdoy_cultist_serpent_heal")
            ctx.extra["token_text"] = "异教徒 再揭示1个标记，若失败：所在及相连地点的巨蛇敌人各治疗2伤害"
            controller._reveal_extra_numeric_token(ctx, "tdoy_cultist_extra")
        elif token == ChaosTokenType.TABLET:
            pending.add("tdoy_tablet_clue_loc")
            ctx.extra["token_text"] = "石板 再揭示1个标记，若失败：所在地点+1线索"
            controller._reveal_extra_numeric_token(ctx, "tdoy_tablet_extra")
        elif token == ChaosTokenType.ELDER_THING:
            if _vengeance(controller) >= 3:
                ctx.extra["force_auto_fail"] = True
                ctx.extra["token_text"] = "旧神之物 自动失败（胜利区复仇点≥3）"
            else:
                v = 4 if hard else 2
                ctx.modify_amount(-v, "tdoy_elder_thing")
                ctx.extra["token_text"] = f"旧神之物 -{v}"

    elif sid == "shattered_aeons":
        if token == ChaosTokenType.SKULL:
            relic = _relic_at_investigator_location(controller, inv)
            x = (5 if relic else 3) if hard else (4 if relic else 2)
            ctx.modify_amount(-x, "sa_skull")
            ctx.extra["token_text"] = f"骷髅 -{x}" + ("（古代遗物在所在地点）" if relic else "")
        elif token == ChaosTokenType.CULTIST:
            v = 3 if hard else 2
            ctx.modify_amount(-v, "sa_cultist")
            if hard:
                pending.add("sa_cultist_doom_each_hard")
                success_pending.add("sa_cultist_doom_each_hard")
                ctx.extra["token_text"] = f"异教徒 -{v}，若未以≥1优势成功：每个异教徒敌人+1毁灭"
            else:
                pending.add("sa_cultist_doom_nearest")
                success_pending.add("sa_cultist_doom_nearest")
                ctx.extra["token_text"] = f"异教徒 -{v}，若未以≥1优势成功：最近异教徒敌人+1毁灭"
        elif token == ChaosTokenType.TABLET:
            if _is_poisoned(controller, inv.investigator_id):
                ctx.extra["force_auto_fail"] = True
                ctx.extra["token_text"] = "石板 自动失败（已中毒）"
            else:
                v = 3 if hard else 2
                ctx.modify_amount(-v, "sa_tablet")
                if hard:
                    pending.add("sa_tablet_poisoned")
                    ctx.extra["token_text"] = f"石板 -{v}，若失败：中毒（Poisoned 弱点置入威胁区）"
                else:
                    ctx.extra["token_text"] = f"石板 -{v}"
        elif token == ChaosTokenType.ELDER_THING:
            v = 3 if hard else 2
            ctx.modify_amount(-v, "sa_elder_thing")
            if hard:
                cid = _shuffle_top_hex_into_explore(controller)
                ctx.extra["token_text"] = (
                    f"旧神之物 -{v}，遭遇弃牌堆顶的 Hex 诡计洗入探索牌堆" + ("" if cid else "（无 Hex 诡计）")
                )
            else:
                pending.add("sa_elder_hex_explore")
                ctx.extra["token_text"] = f"旧神之物 -{v}，若失败：遭遇弃牌堆顶的 Hex 诡计洗入探索牌堆"

    return True


# ---------------------
# 失败/成功结算（由 official_core 分发器在 SKILL_TEST_FAILED/SUCCESSFUL 时调用）
# ---------------------
def _settle(controller, ctx, inv, key: str) -> bool:
    """结算一个 pending key。返回是否认识该 key。"""
    gs = ctx.game_state

    if key in ("wilds_elder_poisoned", "hote_tablet_poisoned", "sa_tablet_poisoned"):
        _mark_poisoned(controller, inv.investigator_id)
        gs.log_effect("💀 标记失败效果：中毒（Poisoned 弱点置入威胁区，简化：vars 标记）")
    elif key == "eztli_elder_doom_loc":
        _add_doom_to_location(controller, inv)
        gs.log_effect("💀 旧神之物失败效果：所在地点+1毁灭")
    elif key == "tof_cultist_damage":
        inv.damage += 1
        gs.log_effect("💀 异教徒效果：未以≥1优势成功，受1伤害")
    elif key == "tof_cultist_direct_hard":
        inv.damage += 1
        gs.log_effect("💀 异教徒效果：未以≥2优势成功，受1直接伤害（简化：按普通伤害）")
    elif key == "tof_tablet_doom_nearest":
        if _doom_nearest_cultist(controller, inv):
            gs.log_effect("💀 石板效果：最近异教徒敌人+1毁灭")
    elif key in ("tof_tablet_doom_each_hard", "tbb_cultist_doom_each_hard",
                 "sa_cultist_doom_each_hard"):
        n = _doom_each_cultist(controller)
        if n:
            gs.log_effect(f"💀 标记效果：{n}个异教徒敌人各+1毁灭")
    elif key == "tof_elder_lose_clue":
        if inv.clues > 0:
            inv.clues -= 1
            gs.log_effect("💀 旧神之物失败效果：失去1个线索")
    elif key in ("tbb_cultist_doom", "sa_cultist_doom_nearest"):
        if _doom_nearest_cultist(controller, inv):
            gs.log_effect("💀 标记效果：最近异教徒敌人+1毁灭（自动选最近，官方为自选）")
    elif key == "tbb_tablet_serpent_attack":
        serpents = _enemy_ids_at(controller, inv.location_id, "serpent")
        if serpents:
            _enemy_attacks(controller, inv, serpents[0])
            gs.log_effect("💀 石板失败效果：所在地点的巨蛇敌人攻击你")
    elif key == "tbb_tablet_serpent_attack_each_hard":
        serpents = _enemy_ids_at(controller, inv.location_id, "serpent")
        for iid in serpents:
            _enemy_attacks(controller, inv, iid)
        if serpents:
            gs.log_effect(f"💀 石板失败效果：{len(serpents)}个巨蛇敌人攻击你")
    elif key == "tbb_elder_clue_ancient":
        if _place_clue_on_nearest_ancient(controller, ctx, inv):
            gs.log_effect("💀 旧神之物失败效果：最近的古代地点+1线索")
    elif key == "hote_cultist_doom_loc":
        _add_doom_to_location(controller, inv)
        gs.log_effect("💀 异教徒失败效果：所在地点+1毁灭")
    elif key == "hote_elder_horror":
        inv.horror += 1
        gs.log_effect("💀 旧神之物失败效果：受1恐惧")
    elif key == "tcoa_symbol_clue":
        if _move_own_clue_to_location(controller, inv):
            gs.log_effect("💀 标记失败效果：将你的1个线索放到所在地点")
    elif key == "tcoa_tablet_discard":
        if inv.hand:
            controller._random_discard_from_hand(inv)
            gs.log_effect("💀 石板失败效果：随机弃1张手牌")
    elif key == "tcoa_tablet_discard_margin_hard":
        margin = max(0, (ctx.difficulty or 0) - (ctx.modified_skill or 0))
        for _ in range(min(margin, len(inv.hand))):
            controller._random_discard_from_hand(inv)
        if margin:
            gs.log_effect(f"💀 石板失败效果：随机弃{margin}张手牌")
    elif key == "tdoy_skull_horror":
        inv.horror += 1
        gs.log_effect("💀 骷髅失败效果：受1恐惧")
    elif key == "tdoy_cultist_serpent_heal":
        n = _heal_serpents_near(controller, inv)
        if n:
            gs.log_effect(f"💀 异教徒失败效果：{n}个巨蛇敌人各治疗2伤害")
    elif key == "tdoy_tablet_clue_loc":
        loc = gs.get_location(inv.location_id)
        if loc is not None:
            loc.clues += 1
            gs.log_effect("💀 石板失败效果：所在地点+1线索")
    elif key == "sa_elder_hex_explore":
        cid = _shuffle_top_hex_into_explore(controller)
        if cid:
            gs.log_effect("💀 旧神之物失败效果：遭遇弃牌堆顶的 Hex 诡计洗入探索牌堆")
    else:
        return False
    return True


def on_fail(controller, ctx, pending) -> None:
    """SKILL_TEST_FAILED 时由 official_core 分发器调用（幂等：结算后移除 key）。"""
    if not pending:
        return
    inv = ctx.game_state.get_investigator(ctx.investigator_id)
    if inv is None:
        return
    for key in list(pending):
        if _settle(controller, ctx, inv, key):
            pending.discard(key)


def on_success(controller, ctx, pending) -> None:
    """SKILL_TEST_SUCCESSFUL 时由 official_core 分发器调用。

    只处理"未以至少 N 点优势成功"类效果：成功但优势不足 N 时仍触发。
    """
    if not pending:
        return
    inv = ctx.game_state.get_investigator(ctx.investigator_id)
    if inv is None:
        return
    margin = (ctx.modified_skill or 0) - (ctx.difficulty or 0)
    for key in list(pending):
        need = _SUCCESS_MARGIN_KEYS.get(key)
        if need is None:
            continue
        if margin < need:
            _settle(controller, ctx, inv, key)
        pending.discard(key)
