"""印斯茅斯阴谋 (The Innsmouth Conspiracy) 八章符号标记效果。

官方文本来源：`data/encounter_cards/innsmouth_conspiracy.json` 的 scenario 卡
`text`（Easy/Standard 正面）与 `back_text`（Hard/Expert 背面）；结构化参考
`.tools/arkham-cards-data/chaos_tokens.json`。冲突以卡面为准。

调用约定（与 official_core 的 _dunwich/_carcosa token 效果一致）：
- `apply_token(controller, ctx, inv, pending, success_pending) -> bool`
  在 CHAOS_TOKEN_RESOLVED 时调用；返回 True 表示该剧本+标记已处理。
- `on_fail(controller, ctx, pending)` 在 SKILL_TEST_FAILED 时结算 pending 标记。
- `on_success(controller, ctx, pending)` 在 SKILL_TEST_SUCCESSFUL 时结算
  （TIC 参考卡正背两面均无“若成功”效果，保留接口作对称）。

TIC 特有机制的简化表示（引擎未实现这些机制，状态存于 `scenario.vars`）：
- `flood_levels`: {location_id: 0|1|2}  0=未淹没 1=部分淹没 2=完全淹没；
  “flooded/已淹没” = 等级 >= 1。
- `keys_controlled`: list[str]  调查员控制的钥匙（全体共享池）。
- `keys_on_locations`: {location_id: [key_id, ...]}  地点上的钥匙。
- `keys_on_scenario_card`: list[str]  剧本参考卡上的钥匙（Lair of Dagon 骷髅）。
- `barriers`: list[frozenset({loc_a, loc_b})]  地点对之间的路障（In Too Deep）。
- `grid_east`: {location_id: east_location_id}  同排东侧邻接（In Too Deep 网格）。
- `road_deck`: list[str]  Road 牌堆剩余地点（Horror in High Gear 骷髅）。
- `in_vehicle`: list[str]  在载具中的调查员 id（Devil Reef 石板）。
- `vehicle_members`: {inv_id: [inv_id, ...]}  同载具成员（Horror in High Gear）；
  缺省时视为只有调查员自己。
- `amalgam_in_depths`: bool  混生畸物是否在深渊中（Pit of Despair 旧神之物）。

简化项（均自动取对玩家最有利/最常用的分支）：
- 选择类效果自动选择：into_the_maelstrom 石板固定选“提高淹没等级”（无法提高才受伤）；
  horror_in_high_gear 异教徒/石板自动选线索/资源最多的同载具成员；
  in_too_deep 石板自动选第一个无路障的连接地点。
- 敌人移动（hunter、“朝你的地点移动”）用 BFS 走一步；“失去 aloof”无对应机制，忽略。
- the_lair_of_dagon 异教徒的“本次检定中揭示过诅咒→自动失败”只检查本次追加揭示的
  那一枚标记（引擎不追踪一次检定内已揭示的标记序列）。
- 官方规则中祝福/诅咒标记揭示后应从袋中移除；本引擎抽标记本来就不从袋中移除，
  故诅咒标记也不做额外移除处理。
- devil_reef 异教徒的“先脱离再重新交战”在机械上等同于保持交战，仅日志体现。
"""

from __future__ import annotations

from typing import Any

from backend.models.enums import CHAOS_TOKEN_VALUES, ChaosTokenType, Skill

TIC_SCENARIO_IDS = {
    "the_vanishing_of_elina_harper",
    "in_too_deep",
    "the_pit_of_despair",
    "devil_reef",
    "horror_in_high_gear",
    "a_light_in_the_fog",
    "the_lair_of_dagon",
    "into_the_maelstrom",
}

_SYMBOL_TOKENS = (
    ChaosTokenType.SKULL,
    ChaosTokenType.CULTIST,
    ChaosTokenType.TABLET,
    ChaosTokenType.ELDER_THING,
)

_TOKEN_NAME_CN = {
    ChaosTokenType.SKULL: "骷髅",
    ChaosTokenType.CULTIST: "异教徒",
    ChaosTokenType.TABLET: "石板",
    ChaosTokenType.ELDER_THING: "旧神之物",
}


# ---------------------------------------------------------------------------
# TIC 机制状态辅助（均读写 scenario.vars）
# ---------------------------------------------------------------------------

def _flood_level(controller, location_id: str) -> int:
    levels = controller.s.vars.get("flood_levels") or {}
    return int(levels.get(location_id, 0) or 0)


def _is_flooded(controller, location_id: str) -> bool:
    return _flood_level(controller, location_id) >= 1


def _increase_flood(controller, location_id: str) -> bool:
    """提高地点淹没等级；已完全淹没（无法提高）时返回 False。"""
    levels = controller.s.vars.setdefault("flood_levels", {})
    level = int(levels.get(location_id, 0) or 0)
    if level >= 2:
        return False
    levels[location_id] = level + 1
    return True


def _keys_controlled(controller) -> list:
    return controller.s.vars.setdefault("keys_controlled", [])


def _keys_on_location(controller, location_id: str) -> list:
    table = controller.s.vars.setdefault("keys_on_locations", {})
    return table.setdefault(location_id, [])


def _place_controlled_keys_on_location(controller, location_id: str) -> int:
    keys = _keys_controlled(controller)
    if not keys:
        return 0
    dest = _keys_on_location(controller, location_id)
    n = len(keys)
    dest.extend(keys)
    keys.clear()
    return n


def _barriers(controller) -> list:
    return controller.s.vars.setdefault("barriers", [])


def _has_barrier(controller, loc_a: str, loc_b: str) -> bool:
    pair = frozenset((loc_a, loc_b))
    return any(frozenset(b) == pair for b in _barriers(controller))


def _barrier_count_at(controller, location_id: str) -> int:
    return sum(1 for b in _barriers(controller) if location_id in frozenset(b))


def _east_of(controller, location_id: str) -> str | None:
    return (controller.s.vars.get("grid_east") or {}).get(location_id)


def _east_chain_count(controller, location_id: str) -> int:
    """同排东侧地点数（沿 grid_east 链，带上限防环）。"""
    count = 0
    cur = location_id
    while count < 20:
        nxt = _east_of(controller, cur)
        if not nxt:
            break
        count += 1
        cur = nxt
    return count


def _unflooded_yha_nthlei_count(controller) -> int:
    n = 0
    for loc in controller.game_state.locations.values():
        traits = [str(t).lower() for t in (loc.card_data.traits or [])] if loc.card_data else []
        if "y'ha-nthlei" in traits and _flood_level(controller, loc.location_id) == 0:
            n += 1
    return n


def _vehicle_members(controller, inv_id: str) -> list[str]:
    members = (controller.s.vars.get("vehicle_members") or {}).get(inv_id)
    if members:
        return [m for m in members if controller.game_state.get_investigator(m) is not None]
    return [inv_id]


def _is_deep_one(controller, instance_id: str | None) -> bool:
    if not instance_id:
        return False
    inst = controller.game_state.get_card_instance(instance_id)
    cd = controller.game_state.get_card_data(inst.card_id) if inst else None
    if cd is None:
        return False
    kws = [str(k).lower() for k in (getattr(cd, "keywords", None) or [])]
    traits = [str(t).lower() for t in (getattr(cd, "traits", None) or [])]
    return "deep_one" in kws or "deep one" in kws or "deep one" in traits


def _engage_investigator(controller, instance_id: str, inv) -> None:
    """敌人与调查员交战（从其他威胁区/地点移除后放入其威胁区）。"""
    state = controller.game_state
    for other in state.investigators.values():
        if instance_id in other.threat_area:
            other.threat_area.remove(instance_id)
    for loc in state.locations.values():
        if instance_id in loc.enemies:
            loc.enemies.remove(instance_id)
    if instance_id not in inv.threat_area:
        inv.threat_area.append(instance_id)


def _place_doom_on_nearest_enemy(controller, inv, n: int = 1) -> bool:
    target = controller._nearest_enemy_with(inv, None)
    if not target:
        return False
    inst = controller.game_state.get_card_instance(target)
    if inst is None:
        return False
    inst.doom += n
    return True


def _place_inv_clue_on_location(controller, inv, n: int = 1) -> int:
    loc = controller.game_state.get_location(inv.location_id)
    if loc is None:
        return 0
    moved = 0
    for _ in range(n):
        if inv.clues <= 0:
            break
        inv.clues -= 1
        loc.clues += 1
        moved += 1
    return moved


def _add_curse_tokens(controller, n: int) -> None:
    for _ in range(n):
        controller.game.chaos_bag.add_token(ChaosTokenType.CURSE)


# ---------------------------------------------------------------------------
# BFS 移动辅助（hunter / “朝你的地点移动”）
# ---------------------------------------------------------------------------

def _bfs_dist(state, from_loc: str, to_loc: str) -> int | None:
    """最短路径距离；不可达返回 None（与 controller._bfs_distance 的 0 区分开）。"""
    if from_loc == to_loc:
        return 0
    visited = {from_loc}
    frontier = [from_loc]
    dist = 0
    while frontier:
        dist += 1
        nxt = []
        for lid in frontier:
            loc = state.get_location(lid)
            for conn in (loc.connections if loc else []):
                if conn == to_loc:
                    return dist
                if conn not in visited:
                    visited.add(conn)
                    nxt.append(conn)
        frontier = nxt
    return None


def _bfs_next_hop(state, from_loc: str, to_loc: str) -> str | None:
    if from_loc == to_loc:
        return None
    visited = {from_loc}
    frontier: list[tuple[str, str | None]] = [(from_loc, None)]
    while frontier:
        cur, first = frontier.pop(0)
        loc = state.get_location(cur)
        for conn in (loc.connections if loc else []):
            hop = first or conn
            if conn == to_loc:
                return hop
            if conn not in visited:
                visited.add(conn)
                frontier.append((conn, hop))
    return None


def _move_enemy_one_hop_toward(state, iid: str, from_loc: str, to_loc: str) -> bool:
    hop = _bfs_next_hop(state, from_loc, to_loc)
    if not hop or hop not in state.locations:
        return False
    src = state.get_location(from_loc)
    if src is None or iid not in src.enemies:
        return False
    src.enemies.remove(iid)
    state.locations[hop].enemies.append(iid)
    return True


def _resolve_hunter_all(controller) -> int:
    """简化版 hunter：场上每个未交战敌人朝最近调查员移动一步。返回移动数。"""
    state = controller.game_state
    inv_locs = [inv.location_id for inv in state.investigators.values()
                if not getattr(inv, "is_defeated", False)]
    moved = 0
    for loc in list(state.locations.values()):
        for iid in list(loc.enemies):
            best_loc, best_d = None, None
            for iloc in inv_locs:
                d = _bfs_dist(state, loc.location_id, iloc)
                if d is not None and (best_d is None or d < best_d):
                    best_d, best_loc = d, iloc
            if best_loc is None or best_d == 0:
                continue
            if _move_enemy_one_hop_toward(state, iid, loc.location_id, best_loc):
                moved += 1
    return moved


def _move_nearest_enemy_toward(controller, inv, *, ready_only: bool) -> str | None:
    """最近的未交战敌人朝调查员地点移动一步。返回敌人 instance_id。"""
    state = controller.game_state
    best = None  # (dist, iid, loc_id)
    for loc in state.locations.values():
        for iid in loc.enemies:
            inst = state.get_card_instance(iid)
            if inst is None:
                continue
            if ready_only and inst.exhausted:
                continue
            d = _bfs_dist(state, loc.location_id, inv.location_id)
            if d is None:
                continue
            if best is None or d < best[0]:
                best = (d, iid, loc.location_id)
    if best is None or best[0] == 0:
        return None
    _, iid, loc_id = best
    if _move_enemy_one_hop_toward(state, iid, loc_id, inv.location_id):
        return iid
    return None


def _reveal_extra_token(controller, ctx, reason: str) -> Any:
    """再揭示1个标记（只取数值修正，不递归触发符号效果），返回该标记。"""
    extra = controller.game.chaos_bag.draw()
    val = CHAOS_TOKEN_VALUES.get(extra) or 0
    ctx.modify_amount(val, reason)
    ctx.extra["token_text"] = (
        f"{ctx.extra.get('token_text', '')}，再揭示[{getattr(extra, 'value', extra)}]"
    )
    return extra


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

def apply_token(controller, ctx, inv, pending, success_pending) -> bool:
    """应用 TIC 剧本的符号标记效果。已处理返回 True，否则 False。"""
    token = ctx.chaos_token
    if token not in _SYMBOL_TOKENS:
        return False
    sid = controller.s.scenario_id
    if sid not in TIC_SCENARIO_IDS or inv is None:
        return False

    hard = controller._is_hard_difficulty
    loc = controller.game_state.get_location(inv.location_id)
    loc_id = inv.location_id
    handler = _SCENARIO_HANDLERS.get(sid)
    if handler is None:
        return False
    handler(controller, ctx, inv, pending, hard, loc, loc_id)

    if ctx.extra.get("token_text"):
        ctx.game_state.log_effect(f"🎲 标记效果：{ctx.extra['token_text']}")
    return True


# ---------------------------------------------------------------------------
# 各剧本效果（front=Easy/Standard，back=Hard/Expert）
# ---------------------------------------------------------------------------

def _veh(controller, ctx, inv, pending, hard, loc, loc_id) -> None:
    """The Vanishing of Elina Harper."""
    token = ctx.chaos_token
    if token == ChaosTokenType.SKULL:
        # -X：X=当前密谋编号（困难面+1）。agenda 1a 编号为 1。
        x = (controller.s.current_agenda_index or 0) + (2 if hard else 1)
        ctx.modify_amount(-x, "veh_skull")
        ctx.extra["token_text"] = f"骷髅 -{x}（当前密谋编号{'+1' if hard else ''}）"
    elif token == ChaosTokenType.CULTIST:
        ctx.modify_amount(-2, "veh_cultist")
        if hard:
            placed = _place_doom_on_nearest_enemy(controller, inv, 1)
            pending.add("veh_cultist_doom_hard")
            ctx.extra["token_text"] = (
                "异教徒 -2，最近敌人+1毁灭（若失败再+1）" if placed
                else "异教徒 -2，场上无敌人（若失败：最近敌人+1毁灭）"
            )
        else:
            pending.add("veh_cultist_doom")
            ctx.extra["token_text"] = "异教徒 -2，若失败：最近敌人+1毁灭"
    elif token == ChaosTokenType.TABLET:
        ctx.modify_amount(-3, "veh_tablet")
        if hard:
            inv.horror += 1
            pending.add("veh_tablet_damage_hard")
            ctx.extra["token_text"] = "石板 -3，受1恐惧（若失败再受1伤害）"
        else:
            pending.add("veh_tablet_horror")
            ctx.extra["token_text"] = "石板 -3，若失败：受1恐惧"
    elif token == ChaosTokenType.ELDER_THING:
        ctx.modify_amount(-4, "veh_elder_thing")
        if hard:
            _place_inv_clue_on_location(controller, inv, 1)
            pending.add("veh_elder_clue_hard")
            ctx.extra["token_text"] = "旧神之物 -4，你的1个线索放到所在地点（若失败再放1个）"
        else:
            pending.add("veh_elder_clue")
            ctx.extra["token_text"] = "旧神之物 -4，若失败：将你的1个线索放到所在地点"


def _itd(controller, ctx, inv, pending, hard, loc, loc_id) -> None:
    """In Too Deep."""
    token = ctx.chaos_token
    if token == ChaosTokenType.SKULL:
        per = 2 if hard else 1
        n = _east_chain_count(controller, loc_id)
        x = per * n
        if x:
            ctx.modify_amount(-x, "itd_skull")
        ctx.extra["token_text"] = f"骷髅 -{x}（东侧同排地点×{n}，每处-{per}）"
    elif token == ChaosTokenType.CULTIST:
        ctx.modify_amount(-4 if hard else -2, "itd_cultist")
        pending.add("itd_cultist_move_east")
        ctx.extra["token_text"] = (
            f"异教徒 {-4 if hard else -2}，若失败：无视路障移到东侧连接地点"
        )
    elif token == ChaosTokenType.TABLET:
        ctx.modify_amount(-5 if hard else -3, "itd_tablet")
        pending.add("itd_tablet_barrier")
        ctx.extra["token_text"] = (
            f"石板 {-5 if hard else -3}，若失败：在你与1个无路障连接地点间放置1路障"
        )
    elif token == ChaosTokenType.ELDER_THING:
        n = _barrier_count_at(controller, loc_id)
        x = n * (2 if hard else 1)
        if x:
            ctx.modify_amount(-x, "itd_elder_thing")
        ctx.extra["token_text"] = (
            f"旧神之物 -{x}（你与连接地点间的路障×{n}{'，翻倍' if hard else ''}）"
        )


def _pod(controller, ctx, inv, pending, hard, loc, loc_id) -> None:
    """The Pit of Despair."""
    token = ctx.chaos_token
    if token == ChaosTokenType.SKULL:
        level = min(2, _flood_level(controller, loc_id))
        values = [-2, -3, -4] if hard else [-1, -2, -3]
        x = values[level]
        ctx.modify_amount(x, "pod_skull")
        note = ("", "（地点部分淹没）", "（地点完全淹没）")[level]
        ctx.extra["token_text"] = f"骷髅 {x}{note}"
    elif token == ChaosTokenType.CULTIST:
        ctx.modify_amount(-2, "pod_cultist")
        flooded = _is_flooded(controller, loc_id)
        if hard:
            if flooded:
                inv.damage += 1
                ctx.extra["token_text"] = "异教徒 -2，地点已淹没：受1伤害"
            else:
                ctx.extra["token_text"] = "异教徒 -2"
        else:
            if flooded:
                pending.add("pod_cultist_damage")
            ctx.extra["token_text"] = "异教徒 -2" + ("，若失败：地点已淹没，受1伤害" if flooded else "")
    elif token == ChaosTokenType.TABLET:
        ctx.modify_amount(-2, "pod_tablet")
        has_key = bool(_keys_controlled(controller))
        if hard:
            if has_key:
                inv.horror += 1
                ctx.extra["token_text"] = "石板 -2，你控制钥匙：受1恐惧"
            else:
                ctx.extra["token_text"] = "石板 -2"
        else:
            if has_key:
                pending.add("pod_tablet_horror")
            ctx.extra["token_text"] = "石板 -2" + ("，若失败：你控制钥匙，受1恐惧" if has_key else "")
    elif token == ChaosTokenType.ELDER_THING:
        ctx.modify_amount(-3, "pod_elder_thing")
        in_depths = bool(controller.s.vars.get("amalgam_in_depths"))
        if hard:
            if in_depths:
                controller._spawn_enemy_from_encounter("the_amalgam", inv.investigator_id)
                ctx.extra["token_text"] = "旧神之物 -3，混生畸物在深渊：放置入场与你交战"
            else:
                ctx.extra["token_text"] = "旧神之物 -3"
        else:
            if in_depths:
                pending.add("pod_elder_amalgam")
            ctx.extra["token_text"] = "旧神之物 -3" + (
                "，若失败：混生畸物在深渊，放置入场与你交战" if in_depths else ""
            )


def _dr(controller, ctx, inv, pending, hard, loc, loc_id) -> None:
    """Devil Reef."""
    token = ctx.chaos_token
    if token == ChaosTokenType.SKULL:
        n = len(_keys_controlled(controller))
        x = n + (1 if hard else 0)
        if x:
            ctx.modify_amount(-x, "dr_skull")
        ctx.extra["token_text"] = f"骷髅 -{x}（调查员控制的钥匙×{n}{'+1' if hard else ''}）"
    elif token == ChaosTokenType.CULTIST:
        ctx.modify_amount(-3 if hard else -2, "dr_cultist")
        is_deep_one_test = (
            ctx.skill_type in (Skill.COMBAT, Skill.AGILITY)
            and _is_deep_one(controller, getattr(ctx, "source", None))
        )
        if hard:
            if is_deep_one_test:
                _engage_investigator(controller, ctx.source, inv)
                ctx.extra["token_text"] = "异教徒 -3，深潜者目标与你交战"
            else:
                ctx.extra["token_text"] = "异教徒 -3"
        else:
            if is_deep_one_test:
                pending.add("dr_cultist_engage")
            ctx.extra["token_text"] = "异教徒 -2" + (
                "，若失败：深潜者目标与你交战" if is_deep_one_test else ""
            )
    elif token == ChaosTokenType.TABLET:
        ctx.modify_amount(-4 if hard else -3, "dr_tablet")
        in_vehicle = inv.investigator_id in (controller.s.vars.get("in_vehicle") or [])
        if hard:
            if not in_vehicle:
                inv.damage += 1
                ctx.extra["token_text"] = "石板 -4，你不在载具中：受1伤害"
            else:
                ctx.extra["token_text"] = "石板 -4"
        else:
            if not in_vehicle:
                pending.add("dr_tablet_damage")
            ctx.extra["token_text"] = "石板 -3" + ("" if in_vehicle else "，若失败：你不在载具中，受1伤害")
    elif token == ChaosTokenType.ELDER_THING:
        ctx.modify_amount(-5 if hard else -4, "dr_elder_thing")
        has_key = bool(_keys_on_location(controller, loc_id))
        if hard:
            if has_key:
                inv.horror += 1
                ctx.extra["token_text"] = "旧神之物 -5，地点有钥匙：受1恐惧"
            else:
                ctx.extra["token_text"] = "旧神之物 -5"
        else:
            if has_key:
                pending.add("dr_elder_horror")
            ctx.extra["token_text"] = "旧神之物 -4" + ("，若失败：地点有钥匙，受1恐惧" if has_key else "")


def _hhg(controller, ctx, inv, pending, hard, loc, loc_id) -> None:
    """Horror in High Gear."""
    token = ctx.chaos_token
    if token == ChaosTokenType.SKULL:
        few = len(controller.s.vars.get("road_deck") or []) <= 6
        x = (-4 if few else -2) if hard else (-3 if few else -1)
        ctx.modify_amount(x, "hhg_skull")
        ctx.extra["token_text"] = f"骷髅 {x}" + ("（Road牌堆≤6）" if few else "")
    elif token == ChaosTokenType.CULTIST:
        ctx.modify_amount(-2 if hard else -1, "hhg_cultist")
        pending.add("hhg_cultist_clues")
        ctx.extra["token_text"] = (
            f"异教徒 {-2 if hard else -1}，若失败：每低于难度1点，"
            "你载具中的1名调查员放1个线索到你所在地点"
        )
    elif token == ChaosTokenType.TABLET:
        ctx.modify_amount(-3 if hard else -2, "hhg_tablet")
        pending.add("hhg_tablet_resources")
        ctx.extra["token_text"] = (
            f"石板 {-3 if hard else -2}，若失败：每低于难度1点，"
            "你载具中的1名调查员失去1资源"
        )
    elif token == ChaosTokenType.ELDER_THING:
        ctx.modify_amount(-4, "hhg_elder_thing")
        if hard:
            n = _resolve_hunter_all(controller)
            ctx.extra["token_text"] = f"旧神之物 -4，结算场上所有敌人的hunter（移动{n}个）"
        else:
            pending.add("hhg_elder_hunter")
            ctx.extra["token_text"] = "旧神之物 -4，若失败：结算场上所有敌人的hunter"


def _litf(controller, ctx, inv, pending, hard, loc, loc_id) -> None:
    """A Light in the Fog."""
    token = ctx.chaos_token
    if token == ChaosTokenType.SKULL:
        ctx.modify_amount(-2 if hard else -1, "litf_skull")
        ctx.extra["token_text"] = f"骷髅 {-2 if hard else -1}"
        if _is_flooded(controller, loc_id):
            _reveal_extra_token(controller, ctx, "litf_skull_extra")
    elif token == ChaosTokenType.CULTIST:
        ctx.modify_amount(-2, "litf_cultist")
        pending.add("litf_cultist_flood")
        ctx.extra["token_text"] = "异教徒 -2，若失败：检定结束后提高你所在地点的淹没等级" + (
            "（无法提高则受1恐惧）" if hard else ""
        )
    elif token == ChaosTokenType.TABLET:
        ctx.modify_amount(-3, "litf_tablet")
        if _is_flooded(controller, loc_id):
            pending.add("litf_tablet_damage")
            ctx.extra["token_text"] = f"石板 -3，若失败：地点已淹没，受{2 if hard else 1}伤害"
        else:
            ctx.extra["token_text"] = "石板 -3"
    elif token == ChaosTokenType.ELDER_THING:
        ctx.modify_amount(-4, "litf_elder_thing")
        if hard:
            moved = _move_nearest_enemy_toward(controller, inv, ready_only=False)
            ctx.extra["token_text"] = "旧神之物 -4，最近未交战敌人朝你的地点移动一步" + (
                "" if moved else "（无敌人可移动）"
            )
        else:
            pending.add("litf_elder_enemy_move")
            ctx.extra["token_text"] = (
                "旧神之物 -4，若失败：最近的就绪未交战敌人朝你的地点移动一步"
            )


def _lod(controller, ctx, inv, pending, hard, loc, loc_id) -> None:
    """The Lair of Dagon."""
    token = ctx.chaos_token
    if token == ChaosTokenType.SKULL:
        per = 2 if hard else 1
        n = len(controller.s.vars.get("keys_on_scenario_card") or [])
        x = per * n
        if x:
            ctx.modify_amount(-x, "lod_skull")
        ctx.extra["token_text"] = f"骷髅 -{x}（本卡上的钥匙×{n}，每把-{per}）"
    elif token == ChaosTokenType.CULTIST:
        ctx.modify_amount(-2 if hard else 0, "lod_cultist")
        ctx.extra["token_text"] = f"异教徒 {-2 if hard else 0}"
        extra = _reveal_extra_token(controller, ctx, "lod_cultist_extra")
        if extra == ChaosTokenType.CURSE:
            ctx.extra["force_auto_fail"] = True
            ctx.extra["token_text"] += "，揭示诅咒：自动失败"
    elif token == ChaosTokenType.TABLET:
        ctx.modify_amount(-3, "lod_tablet")
        if hard:
            n = _place_controlled_keys_on_location(controller, loc_id)
            inv.damage += 1
            ctx.extra["token_text"] = f"石板 -3，你控制的钥匙（{n}把）放到所在地点，受1伤害"
        else:
            pending.add("lod_tablet_keys")
            ctx.extra["token_text"] = "石板 -3，若失败：你控制的每把钥匙放到所在地点"
    elif token == ChaosTokenType.ELDER_THING:
        ctx.modify_amount(-4, "lod_elder_thing")
        if hard:
            _add_curse_tokens(controller, 2)
            ctx.extra["token_text"] = "旧神之物 -4，混沌袋+2诅咒"
        else:
            pending.add("lod_elder_curse")
            ctx.extra["token_text"] = "旧神之物 -4，若失败：混沌袋+1诅咒"


def _itm(controller, ctx, inv, pending, hard, loc, loc_id) -> None:
    """Into the Maelstrom."""
    token = ctx.chaos_token
    if token == ChaosTokenType.SKULL:
        many = _unflooded_yha_nthlei_count(controller) >= 4
        x = (-4 if many else -2) if hard else (-3 if many else -1)
        ctx.modify_amount(x, "itm_skull")
        ctx.extra["token_text"] = f"骷髅 {x}" + ("（未淹没Y'ha-nthlei地点≥4）" if many else "")
    elif token == ChaosTokenType.CULTIST:
        ctx.modify_amount(-4 if hard else -3, "itm_cultist")
        pending.add("itm_cultist_doom")
        ctx.extra["token_text"] = (
            f"异教徒 {-4 if hard else -3}，若失败：当前密谋+1毁灭（可能推进密谋）"
        )
    elif token == ChaosTokenType.TABLET:
        ctx.modify_amount(-5 if hard else -4, "itm_tablet")
        pending.add("itm_tablet_flood_or_damage")
        ctx.extra["token_text"] = (
            f"石板 {-5 if hard else -4}，若失败：提高所在地点淹没等级或受1伤害"
        )
    elif token == ChaosTokenType.ELDER_THING:
        ctx.modify_amount(-6 if hard else -5, "itm_elder_thing")
        if _keys_on_location(controller, loc_id):
            pending.add("itm_elder_horror")
            ctx.extra["token_text"] = (
                f"旧神之物 {-6 if hard else -5}，若失败：地点有钥匙，受1恐惧"
            )
        else:
            ctx.extra["token_text"] = f"旧神之物 {-6 if hard else -5}"


_SCENARIO_HANDLERS = {
    "the_vanishing_of_elina_harper": _veh,
    "in_too_deep": _itd,
    "the_pit_of_despair": _pod,
    "devil_reef": _dr,
    "horror_in_high_gear": _hhg,
    "a_light_in_the_fog": _litf,
    "the_lair_of_dagon": _lod,
    "into_the_maelstrom": _itm,
}


# ---------------------------------------------------------------------------
# 失败/成功结算
# ---------------------------------------------------------------------------

def on_fail(controller, ctx, pending) -> None:
    """SKILL_TEST_FAILED 时结算 TIC token 的条件效果。"""
    if not pending:
        return
    inv = ctx.game_state.get_investigator(ctx.investigator_id)
    if inv is None:
        return
    log = ctx.game_state.log_effect

    # --- The Vanishing of Elina Harper ---
    if "veh_cultist_doom" in pending:
        if _place_doom_on_nearest_enemy(controller, inv, 1):
            log("💀 异教徒失败效果：最近敌人+1毁灭")
        pending.discard("veh_cultist_doom")
    if "veh_cultist_doom_hard" in pending:
        if _place_doom_on_nearest_enemy(controller, inv, 1):
            log("💀 异教徒失败效果：最近敌人再+1毁灭（共2）")
        pending.discard("veh_cultist_doom_hard")
    if "veh_tablet_horror" in pending:
        inv.horror += 1
        log("💀 石板失败效果：受1恐惧")
        pending.discard("veh_tablet_horror")
    if "veh_tablet_damage_hard" in pending:
        inv.damage += 1
        log("💀 石板失败效果：再受1伤害")
        pending.discard("veh_tablet_damage_hard")
    if "veh_elder_clue" in pending:
        if _place_inv_clue_on_location(controller, inv, 1):
            log("💀 旧神之物失败效果：你的1个线索放到所在地点")
        pending.discard("veh_elder_clue")
    if "veh_elder_clue_hard" in pending:
        if _place_inv_clue_on_location(controller, inv, 1):
            log("💀 旧神之物失败效果：再放1个线索到所在地点（共2）")
        pending.discard("veh_elder_clue_hard")

    # --- In Too Deep ---
    if "itd_cultist_move_east" in pending:
        dest = _east_of(controller, inv.location_id)
        if dest and controller.game_state.get_location(dest) is not None:
            inv.location_id = dest
            log(f"💀 异教徒失败效果：无视路障移到东侧地点【{dest}】")
        pending.discard("itd_cultist_move_east")
    if "itd_tablet_barrier" in pending:
        loc = controller.game_state.get_location(inv.location_id)
        conns = list(loc.connections) if loc else []
        placed = None
        for conn in conns:
            if not _has_barrier(controller, inv.location_id, conn):
                placed = conn
                break
        if placed is not None:
            _barriers(controller).append(frozenset((inv.location_id, placed)))
            log(f"💀 石板失败效果：在【{inv.location_id}】与【{placed}】之间放置1路障")
        pending.discard("itd_tablet_barrier")

    # --- The Pit of Despair ---
    if "pod_cultist_damage" in pending:
        inv.damage += 1
        log("💀 异教徒失败效果：地点已淹没，受1伤害")
        pending.discard("pod_cultist_damage")
    if "pod_tablet_horror" in pending:
        inv.horror += 1
        log("💀 石板失败效果：你控制钥匙，受1恐惧")
        pending.discard("pod_tablet_horror")
    if "pod_elder_amalgam" in pending:
        controller._spawn_enemy_from_encounter("the_amalgam", inv.investigator_id)
        log("💀 旧神之物失败效果：混生畸物放置入场与你交战")
        pending.discard("pod_elder_amalgam")

    # --- Devil Reef ---
    if "dr_cultist_engage" in pending:
        source = getattr(ctx, "source", None)
        if _is_deep_one(controller, source):
            _engage_investigator(controller, source, inv)
            log("💀 异教徒失败效果：深潜者目标与你交战")
        pending.discard("dr_cultist_engage")
    if "dr_tablet_damage" in pending:
        inv.damage += 1
        log("💀 石板失败效果：你不在载具中，受1伤害")
        pending.discard("dr_tablet_damage")
    if "dr_elder_horror" in pending:
        inv.horror += 1
        log("💀 旧神之物失败效果：地点有钥匙，受1恐惧")
        pending.discard("dr_elder_horror")

    # --- Horror in High Gear ---
    if "hhg_cultist_clues" in pending:
        margin = max(0, (ctx.difficulty or 0) - (ctx.modified_skill or 0))
        loc = controller.game_state.get_location(inv.location_id)
        members = _vehicle_members(controller, inv.investigator_id)
        moved = 0
        for _ in range(margin):
            candidates = [m for m in members
                          if (controller.game_state.get_investigator(m).clues or 0) > 0]
            if not candidates or loc is None:
                break
            best = max(candidates,
                       key=lambda m: controller.game_state.get_investigator(m).clues)
            bi = controller.game_state.get_investigator(best)
            bi.clues -= 1
            loc.clues += 1
            moved += 1
        if moved:
            log(f"💀 异教徒失败效果：载具成员放{moved}个线索到所在地点")
        pending.discard("hhg_cultist_clues")
    if "hhg_tablet_resources" in pending:
        margin = max(0, (ctx.difficulty or 0) - (ctx.modified_skill or 0))
        members = _vehicle_members(controller, inv.investigator_id)
        lost = 0
        for _ in range(margin):
            candidates = [m for m in members
                          if (controller.game_state.get_investigator(m).resources or 0) > 0]
            if not candidates:
                break
            best = max(candidates,
                       key=lambda m: controller.game_state.get_investigator(m).resources)
            bi = controller.game_state.get_investigator(best)
            bi.resources -= 1
            lost += 1
        if lost:
            log(f"💀 石板失败效果：载具成员失去{lost}资源")
        pending.discard("hhg_tablet_resources")
    if "hhg_elder_hunter" in pending:
        n = _resolve_hunter_all(controller)
        log(f"💀 旧神之物失败效果：结算hunter（移动{n}个敌人）")
        pending.discard("hhg_elder_hunter")

    # --- A Light in the Fog ---
    if "litf_cultist_flood" in pending:
        if _increase_flood(controller, inv.location_id):
            log("💀 异教徒失败效果：所在地点淹没等级提高")
        elif controller._is_hard_difficulty:
            inv.horror += 1
            log("💀 异教徒失败效果：无法提高淹没等级，受1恐惧")
        pending.discard("litf_cultist_flood")
    if "litf_tablet_damage" in pending:
        n = 2 if controller._is_hard_difficulty else 1
        inv.damage += n
        log(f"💀 石板失败效果：地点已淹没，受{n}伤害")
        pending.discard("litf_tablet_damage")
    if "litf_elder_enemy_move" in pending:
        moved = _move_nearest_enemy_toward(controller, inv, ready_only=True)
        if moved:
            log("💀 旧神之物失败效果：最近的就绪未交战敌人朝你的地点移动一步")
        pending.discard("litf_elder_enemy_move")

    # --- The Lair of Dagon ---
    if "lod_tablet_keys" in pending:
        n = _place_controlled_keys_on_location(controller, inv.location_id)
        if n:
            log(f"💀 石板失败效果：你控制的{n}把钥匙放到所在地点")
        pending.discard("lod_tablet_keys")
    if "lod_elder_curse" in pending:
        _add_curse_tokens(controller, 1)
        log("💀 旧神之物失败效果：混沌袋+1诅咒")
        pending.discard("lod_elder_curse")

    # --- Into the Maelstrom ---
    if "itm_cultist_doom" in pending:
        ctx.game_state.scenario.doom_on_agenda += 1
        controller._check_agenda_threshold()
        log("💀 异教徒失败效果：当前密谋+1毁灭")
        pending.discard("itm_cultist_doom")
    if "itm_tablet_flood_or_damage" in pending:
        # 简化：自动选“提高淹没等级”，无法提高才受1伤害
        if _increase_flood(controller, inv.location_id):
            log("💀 石板失败效果：所在地点淹没等级提高")
        else:
            inv.damage += 1
            log("💀 石板失败效果：无法提高淹没等级，受1伤害")
        pending.discard("itm_tablet_flood_or_damage")
    if "itm_elder_horror" in pending:
        inv.horror += 1
        log("💀 旧神之物失败效果：地点有钥匙，受1恐惧")
        pending.discard("itm_elder_horror")


def on_success(controller, ctx, pending) -> None:
    """SKILL_TEST_SUCCESSFUL 时结算。

    TIC 八个剧本参考卡正背两面均无“若成功”效果，保留此入口与
    official_core 的 _scenario_token_success_effects 对称。
    """
    return None
