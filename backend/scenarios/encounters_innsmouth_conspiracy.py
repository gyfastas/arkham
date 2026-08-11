"""The Innsmouth Conspiracy encounter treachery resolution.

Called from ScenarioController.resolve_encounter_card as a fallback after the
Carcosa/Dunwich branches (wiring lives in official_core.py). Each handler
returns {"pending": bool, "message": str} (plus "surge": True when the card
surges) or None to continue to the next matcher. Choice cards set
`scenario.vars["pending_choice"]` (with an "investigator_id" field for
multiplayer routing) and are re-entered with `choice=<option_id>`.

Cycle-wide state conventions (all live in `scenario.vars`, since the engine
has no native model for these Innsmouth mechanics — see "Engine gaps"):

- `flood_levels`: {location_id: 0|1|2} — 0 未淹没 / 1 部分淹没 / 2 完全淹没。
  Written by rising_tides/tidal_alignment/treacherous_depths; read by the
  flooded-conditional cards (undertow/riptide/shapes_in_the_water/...).
- `vehicles`: {investigator_id: {"vehicle": card_id, "driver": bool}} —
  who is in which vehicle and who drives it (injected by the scenario layer).
- `keys`: {investigator_id: [key_id, ...]} investigator-controlled keys;
  `location_keys`: {location_id: [key_id, ...]} keys placed on locations.
- `barriers`: [[loc_a, loc_b], ...] unordered location pairs with a barrier.
- `location_grid`: {location_id: (row, col)} — optional grid for the
  east/rearmost logic of deep_one_invasion/pulled_back/theyre_catching_up.
- `the_depths`: [card_id, ...] — The Amalgam's "depths" pile.

Engine gaps (recorded in vars, NOT enforced — no hook points without touching
the engine; documented per card below):

- Flood levels have no gameplay effects beyond what the cards above do.
- "Cannot parley" (furtive_locals), "+1 shroud per location"
  (fog_over_innsmouth), "reveal an additional token when attacking at a
  flooded location" (aquatic_ambush), "cannot gain resources/draw cards"
  (kiss_of_brine), "cannot enter vehicles" (dragged_under), movement blocking
  (stone_barrier), Oceiros Marsh's double-hunter/+1/+1 attack
  (worth_his_salt), capture (taken_captive), investigator trait granting
  (innsmouth_look's Deep One trait).
- Peril ("cannot commit cards") is not enforced by the session layer here;
  noted on tidal_alignment/syzygy/treacherous_depths/conspiracy_of_deep_ones.

Other simplifications (documented per card):

- "Choose and discard" picks deterministically (cheapest asset / first cards).
- "You must either X or Y" inside failed tests resolves deterministically.
- Investigator choices that officially happen *after* a test succeeds
  (fog_over_innsmouth/furtive_locals) are asked up front via pending_choice.
- "Nearest" uses BFS over the location connection graph.
- TIC encounter data stores traits in English ("deep one"); tag checks here
  normalize "_" / " " and scan both `keywords` and `traits`.
"""

from __future__ import annotations

import random
from typing import Any

from backend.models.enums import ChaosTokenType, GameEvent, Skill, TimingPriority
from backend.models.state import CardInstance

THE_AMALGAM = "the_amalgam"
HOLDING_CELLS = "holding_cells"
_BLESS_CURSE_CAP = 10  # 官方规则：混乱袋中祝福+诅咒合计最多10


# ---------------------------------------------------------------------------
# 通用辅助
# ---------------------------------------------------------------------------

def _margin_fail(result) -> int:
    return max(0, (getattr(result, "difficulty", 0) or 0) - (getattr(result, "modified_skill", 0) or 0))


def _log_names(game, cids: list[str]) -> str:
    return "、".join(game.state.card_name(c) for c in cids)


def _norm(tag: str) -> str:
    return str(tag).lower().replace("_", " ").strip()


def _tags_of(game, instance_id: str) -> list[str]:
    """Enemy keyword+trait union, normalized (TIC data keeps English traits)."""
    inst = game.state.get_card_instance(instance_id)
    if inst is None:
        return []
    cd = game.state.get_card_data(inst.card_id)
    if cd is None:
        return []
    raw = list(getattr(cd, "keywords", None) or []) + list(getattr(cd, "traits", None) or [])
    return [_norm(t) for t in raw]


def _has_tag(tags: list[str], tag: str) -> bool:
    return _norm(tag) in tags


def _card_has_tag(cd, tag: str) -> bool:
    if cd is None:
        return False
    raw = list(getattr(cd, "keywords", None) or []) + list(getattr(cd, "traits", None) or [])
    return _norm(tag) in [_norm(t) for t in raw]


def _is_enemy_with_tag(game, card_id: str, tag: str) -> bool:
    cd = game.state.get_card_data(card_id)
    if cd is None or cd.type.value != "enemy":
        return False
    return _card_has_tag(cd, tag)


def _enemies_with_tag(game, tag: str) -> list[str]:
    out = []
    for iid, inst in game.state.cards_in_play.items():
        cd = game.state.get_card_data(inst.card_id)
        if cd is None or cd.type.value != "enemy":
            continue
        if _has_tag(_tags_of(game, iid), tag):
            out.append(iid)
    return out


def _place_in_threat(game, inv, card_id: str) -> str:
    inst_id = game.state.next_instance_id()
    ci = CardInstance(
        instance_id=inst_id, card_id=card_id,
        owner_id=inv.investigator_id, controller_id=inv.investigator_id,
    )
    game.state.cards_in_play[inst_id] = ci
    inv.threat_area.append(inst_id)
    return inst_id


def _threat_copy(game, inv, card_id: str) -> str | None:
    for iid in inv.threat_area:
        inst = game.state.get_card_instance(iid)
        if inst is not None and inst.card_id == card_id:
            return iid
    return None


def _remove_from_threat(game, inv, instance_id: str, *, to_encounter_discard: bool = True) -> None:
    inst = game.state.cards_in_play.pop(instance_id, None)
    if inst is not None and instance_id in inv.threat_area:
        inv.threat_area.remove(instance_id)
        if to_encounter_discard:
            game.state.scenario.encounter_discard.append(inst.card_id)


def _enemy_location(game, instance_id: str) -> str | None:
    """Location holding the enemy, or the engaged investigator's location."""
    for loc in game.state.locations.values():
        if instance_id in loc.enemies:
            return loc.location_id
    for inv in game.state.investigators.values():
        if instance_id in inv.threat_area:
            return inv.location_id
    return None


def _unengaged_location(game, instance_id: str) -> str | None:
    for loc in game.state.locations.values():
        if instance_id in loc.enemies:
            return loc.location_id
    return None


def _engage_investigator(game, instance_id: str, inv) -> None:
    """Move enemy to the investigator's location and engage them."""
    for loc in game.state.locations.values():
        if instance_id in loc.enemies:
            loc.enemies.remove(instance_id)
    for other in game.state.investigators.values():
        if instance_id in other.threat_area:
            other.threat_area.remove(instance_id)
    if instance_id not in inv.threat_area:
        inv.threat_area.append(instance_id)


def _enemy_attack(game, instance_id: str, investigator_id: str) -> None:
    inst = game.state.get_card_instance(instance_id)
    cd = game.state.get_card_data(inst.card_id) if inst else None
    if cd is None:
        return
    game.damage_engine.deal_damage(
        investigator_id, damage=cd.enemy_damage or 0,
        horror=cd.enemy_horror or 0, source=instance_id)


def _spawn_enemy_at(game, card_id: str, location_id: str) -> str:
    """Spawn an enemy unengaged at a specific location."""
    inst_id = game.state.next_instance_id()
    ci = CardInstance(
        instance_id=inst_id, card_id=card_id,
        owner_id="scenario", controller_id="scenario",
    )
    game.state.cards_in_play[inst_id] = ci
    loc = game.state.get_location(location_id)
    if loc is not None:
        loc.enemies.append(inst_id)
    return inst_id


def _register_one_shot(game, event: GameEvent, handler) -> None:
    """Register an event handler that unregisters itself after firing once."""
    holder: list[Any] = []

    def _wrap(ctx):
        entry = holder[0]
        game.event_bus.unregister(entry)
        handler(ctx)

    holder.append(game.event_bus.register(event, _wrap, priority=TimingPriority.AFTER))


def _bfs_distances(game, start: str) -> dict[str, int]:
    """Distance map over the location connection graph (start=0)."""
    dist = {start: 0}
    frontier = [start]
    while frontier:
        nxt = []
        for lid in frontier:
            loc = game.state.get_location(lid)
            if loc is None:
                continue
            for conn in loc.connections:
                if conn not in dist:
                    dist[conn] = dist[lid] + 1
                    nxt.append(conn)
        frontier = nxt
    return dist


def _nearest_location(game, from_location_id: str, predicate) -> str | None:
    """Nearest location (BFS; ties favor the lower distance then first found)
    satisfying predicate(loc_id). Includes the origin itself."""
    dist = _bfs_distances(game, from_location_id)
    best = None
    best_d = None
    for loc_id in game.state.locations:
        if loc_id not in dist or not predicate(loc_id):
            continue
        d = dist[loc_id]
        if best_d is None or d < best_d:
            best, best_d = loc_id, d
    return best


def _auto_discard_play_assets(controller, inv, x: int) -> list[str]:
    """Greedy-discard cheapest assets from the play area until total printed
    cost >= X. Auto-selection simplification: officially chosen by player."""
    game = controller.game
    if x <= 0:
        return []
    candidates: list[tuple[int, str]] = []
    for iid in inv.play_area:
        inst = game.state.get_card_instance(iid)
        cd = game.state.get_card_data(inst.card_id) if inst else None
        if cd is None or cd.type.value != "asset":
            continue
        candidates.append((cd.cost or 0, iid))
    candidates.sort(key=lambda t: t[0])
    discarded: list[str] = []
    total = 0
    for cost, iid in candidates:
        if total >= x:
            break
        inst = game.state.get_card_instance(iid)
        discarded.append(inst.card_id if inst else iid)
        game.damage_engine._remove_card_from_play(iid)
        total += cost
    return discarded


def _discard_cheapest_asset(controller, inv) -> str | None:
    """Discard the cheapest asset the investigator controls. Returns card_id."""
    game = controller.game
    best = None
    best_cost = None
    for iid in inv.play_area:
        inst = game.state.get_card_instance(iid)
        cd = game.state.get_card_data(inst.card_id) if inst else None
        if cd is None or cd.type.value != "asset":
            continue
        cost = cd.cost or 0
        if best_cost is None or cost < best_cost:
            best, best_cost = iid, cost
    if best is None:
        return None
    inst = game.state.get_card_instance(best)
    cid = inst.card_id if inst else best
    game.damage_engine._remove_card_from_play(best)
    return cid


def _discard_hand_cards(inv, n: int) -> list[str]:
    """Discard the first N hand cards (auto-selection simplification)."""
    out = []
    for cid in list(inv.hand)[:max(0, n)]:
        inv.hand.remove(cid)
        inv.discard.append(cid)
        out.append(cid)
    return out


# ---------------------------------------------------------------------------
# 循环机制状态（flood / vehicle / keys / barriers / depths / grid）
# ---------------------------------------------------------------------------

def _flood_level(game, location_id: str) -> int:
    return int(game.state.scenario.vars.get("flood_levels", {}).get(location_id, 0) or 0)


def _is_flooded(game, location_id: str) -> bool:
    return _flood_level(game, location_id) >= 1


def _is_fully_flooded(game, location_id: str) -> bool:
    return _flood_level(game, location_id) >= 2


def _increase_flood(game, location_id: str) -> bool:
    """Raise the flood level by 1 (cap 2). Returns True if it increased."""
    levels = game.state.scenario.vars.setdefault("flood_levels", {})
    cur = int(levels.get(location_id, 0) or 0)
    if cur >= 2:
        levels[location_id] = 2
        return False
    levels[location_id] = cur + 1
    return True


def _vehicle_record(game, investigator_id: str) -> dict | None:
    return game.state.scenario.vars.get("vehicles", {}).get(investigator_id)


def _in_vehicle(game, investigator_id: str) -> bool:
    return _vehicle_record(game, investigator_id) is not None


def _vehicle_mates(game, investigator_id: str) -> list[str]:
    """All investigators in the same vehicle as the given one (incl. itself)."""
    rec = _vehicle_record(game, investigator_id)
    if rec is None:
        return []
    vid = rec.get("vehicle")
    return [iid for iid, r in game.state.scenario.vars.get("vehicles", {}).items()
            if r.get("vehicle") == vid]


def _vehicle_driver(game, investigator_id: str) -> str:
    """Driver of the given investigator's vehicle (fallback: themselves)."""
    for iid in _vehicle_mates(game, investigator_id):
        if _vehicle_record(game, iid).get("driver"):
            return iid
    return investigator_id


def _leave_vehicle(game, investigator_id: str) -> None:
    game.state.scenario.vars.get("vehicles", {}).pop(investigator_id, None)


def _keys_of(game, investigator_id: str) -> list[str]:
    return game.state.scenario.vars.setdefault("keys", {}).setdefault(investigator_id, [])


def _place_keys_on_location(game, investigator_id: str, location_id: str) -> int:
    """Move each key the investigator controls onto the location. Returns count."""
    keys = _keys_of(game, investigator_id)
    if not keys:
        return 0
    loc_keys = game.state.scenario.vars.setdefault("location_keys", {}).setdefault(location_id, [])
    n = 0
    for k in list(keys):
        keys.remove(k)
        loc_keys.append(k)
        n += 1
    return n


def _location_has_key(game, location_id: str) -> bool:
    return bool(game.state.scenario.vars.get("location_keys", {}).get(location_id))


def _barriers(game) -> list:
    return game.state.scenario.vars.setdefault("barriers", [])


def _has_barrier(game, a: str, b: str) -> bool:
    return [a, b] in _barriers(game) or [b, a] in _barriers(game)


def _add_barrier(game, a: str, b: str) -> bool:
    if _has_barrier(game, a, b):
        return False
    _barriers(game).append([a, b])
    return True


def _grid(game) -> dict:
    return game.state.scenario.vars.get("location_grid", {})


def _east_locations(game, location_id: str) -> list[str]:
    """Locations due east (same row, greater column), nearest first."""
    grid = _grid(game)
    pos = grid.get(location_id)
    if pos is None:
        return []
    row, col = pos
    east = [(c, lid) for lid, (r, c) in grid.items() if r == row and c > col]
    east.sort()
    return [lid for _c, lid in east]


def _rearmost_location(game, fallback: str) -> str:
    grid = _grid(game)
    if not grid:
        return fallback
    return max(grid.items(), key=lambda kv: (kv[1][1], kv[1][0]))[0]


def _depths(game) -> list[str]:
    return game.state.scenario.vars.setdefault("the_depths", [])


def _amalgam_in_play(game) -> str | None:
    for iid, inst in game.state.cards_in_play.items():
        if inst.card_id == THE_AMALGAM:
            return iid
    return None


def _remove_from_play(game, instance_id: str) -> None:
    for loc in game.state.locations.values():
        if instance_id in loc.enemies:
            loc.enemies.remove(instance_id)
    for inv in game.state.investigators.values():
        if instance_id in inv.threat_area:
            inv.threat_area.remove(instance_id)
        if instance_id in inv.play_area:
            inv.play_area.remove(instance_id)
    game.state.cards_in_play.pop(instance_id, None)


# ---------------------------------------------------------------------------
# 检定期间的标记观察（诅咒/异教徒/石板/旧神之物）
# ---------------------------------------------------------------------------

def _watch_tokens(game, investigator_id: str, tokens: set,
                  on_reveal=None) -> dict:
    """Observe chaos tokens revealed during the investigator's next skill test.

    Returns a record {"count": int}. Handlers self-unregister when that
    investigator's skill test ends (SKILL_TEST_ENDS).
    """
    record: dict[str, Any] = {"count": 0}
    holder: list[Any] = []

    def _on_token(ctx):
        if ctx.investigator_id != investigator_id:
            return
        if ctx.chaos_token in tokens:
            record["count"] += 1
            if on_reveal is not None:
                on_reveal(ctx)

    def _on_end(ctx):
        if ctx.investigator_id != investigator_id:
            return
        for entry in holder:
            game.event_bus.unregister(entry)

    holder.append(game.event_bus.register(
        GameEvent.CHAOS_TOKEN_RESOLVED, _on_token, priority=TimingPriority.WHEN))
    holder.append(game.event_bus.register(
        GameEvent.SKILL_TEST_ENDS, _on_end, priority=TimingPriority.AFTER))
    return record


def _run_test_full(controller, investigator_id: str, *, skill, difficulty: int,
                   on_success=None, on_failure=None) -> None:
    """controller._run_skill_test 的双回调版本（供连续检定/成功分支使用）。

    会话层设置了 skill_test_request_handler 时同样由其接管投入/揭示流程。
    """
    def _ok(r):
        if on_success:
            on_success(r)

    def _fail(r):
        if on_failure:
            on_failure(r)

    if controller.skill_test_request_handler is not None:
        controller.skill_test_request_handler(
            investigator_id=investigator_id,
            skill=skill,
            difficulty=difficulty,
            on_success=_ok,
            on_failure=_fail,
        )
        return
    controller.game.skill_test_engine.run_test(
        investigator_id=investigator_id,
        skill_type=skill,
        difficulty=difficulty,
        committed_card_ids=[],
        on_success=_ok,
        on_failure=_fail,
    )


def _put_next_to_agenda(game, card_id: str) -> None:
    """Put a treachery into play next to the agenda deck (counted in vars);
    one copy is discarded at each round end (max once per round)."""
    counts = game.state.scenario.vars.setdefault("next_to_agenda", {})
    counts[card_id] = counts.get(card_id, 0) + 1
    if counts[card_id] == 1:
        _register_agenda_side_sweeper(game, card_id)


def _register_agenda_side_sweeper(game, card_id: str) -> None:
    holder: list[Any] = []

    def _sweep(_ctx):
        counts = game.state.scenario.vars.get("next_to_agenda", {})
        n = int(counts.get(card_id, 0) or 0)
        if n <= 1:
            counts.pop(card_id, None)
            game.event_bus.unregister(holder[0])
            game.state.scenario.encounter_discard.append(card_id)
        else:
            counts[card_id] = n - 1

    holder.append(game.event_bus.register(GameEvent.ROUND_ENDS, _sweep,
                                          priority=TimingPriority.AFTER))


def _resolve_hunter_step(game, instance_id: str) -> bool:
    """Resolve the hunter keyword on one enemy. Returns True if it MOVED
    (engagement without movement does not count)."""
    loc_id = _unengaged_location(game, instance_id)
    if loc_id is None:
        return False  # 已交战的猎手不移动
    inst = game.state.get_card_instance(instance_id)
    if inst is None or inst.exhausted:
        return False
    target_inv, first_hop = game.enemy_phase._hunter_first_step(loc_id)
    if target_inv is None:
        return False
    loc = game.state.get_location(loc_id)
    if first_hop is None:
        # 与调查员同地点：交战（不算移动）
        loc.enemies.remove(instance_id)
        target_inv.threat_area.append(instance_id)
        return False
    dest = game.state.get_location(first_hop)
    if dest is None:
        return False
    loc.enemies.remove(instance_id)
    at_dest = game.state.get_investigators_at_location(first_hop)
    if at_dest:
        at_dest[0].threat_area.append(instance_id)
    else:
        dest.enemies.append(instance_id)
    return True


def _pull_enemy_by_tag(game, tag: str, *, extra=None) -> str | None:
    """Search encounter deck then discard for an enemy matching the tag
    (and the optional extra predicate on card data)."""
    s = game.state.scenario
    for pile in (s.encounter_deck, s.encounter_discard):
        for cid in list(pile):
            cd = game.state.get_card_data(cid)
            if cd is None or cd.type.value != "enemy":
                continue
            if not _card_has_tag(cd, tag):
                continue
            if extra is not None and not extra(cd):
                continue
            pile.remove(cid)
            return cid
    return None


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

def resolve_treachery(controller, card_id: str, *, investigator_id: str,
                      choice: str | None = None) -> dict | None:
    """Resolve an Innsmouth Conspiracy treachery. Returns result dict, or None."""
    game = controller.game
    inv = game.state.get_investigator(investigator_id)
    if inv is None:
        return None
    log = controller.log
    run_test = controller._run_skill_test
    svars = game.state.scenario.vars

    # ---- In Too Deep（混生畸物 Scheme）----
    if card_id == "blindsense":
        log("👁️ 遭遇：有眼无珠（敏捷3，失败：混生畸物就绪/入场、交战并立即攻击）")

        def on_fail(_r):
            iid = _amalgam_in_play(game)
            if iid is not None:
                inst = game.state.get_card_instance(iid)
                if inst is not None:
                    inst.exhausted = False
                # 简化：直接移至调查员地点交战（官方逐地点移动，结果相同）
                _engage_investigator(game, iid, inv)
                _enemy_attack(game, iid, investigator_id)
                log("  → 混生畸物就绪、与你交战并立即攻击")
            elif THE_AMALGAM in _depths(game):
                _depths(game).remove(THE_AMALGAM)
                new_id = game.state.next_instance_id()
                game.state.cards_in_play[new_id] = CardInstance(
                    instance_id=new_id, card_id=THE_AMALGAM,
                    owner_id="scenario", controller_id="scenario")
                inv.threat_area.append(new_id)
                _enemy_attack(game, new_id, investigator_id)
                log("  → 混生畸物从深渊中入场，与你交战并立即攻击")
            else:
                log("  → 混生畸物不在场也不在深渊，无效果")
        run_test(investigator_id, skill=Skill.AGILITY, difficulty=3, on_failure=on_fail)
        return {"pending": False, "message": "blindsense"}

    if card_id == "from_the_depths":
        if THE_AMALGAM in _depths(game):
            _depths(game).remove(THE_AMALGAM)
            new_id = game.state.next_instance_id()
            game.state.cards_in_play[new_id] = CardInstance(
                instance_id=new_id, card_id=THE_AMALGAM,
                owner_id="scenario", controller_id="scenario")
            inv.threat_area.append(new_id)
            log("🌊 遭遇：来自深渊——混生畸物从深渊中入场，与你交战")
            return {"pending": False, "message": "from_the_depths"}
        iid = _amalgam_in_play(game)
        if iid is not None:
            _remove_from_play(game, iid)
        _depths(game).append(THE_AMALGAM)
        log("🌊 遭遇：来自深渊——混生畸物放入深渊，涌动")
        return {"pending": False, "message": "surge", "surge": True}

    # ---- The Vanishing of Elina Harper ----
    if card_id == "psychic_pull":
        if not inv.hand:
            log("🧠 遭遇：魂牵梦绕——无手牌，涌动")
            return {"pending": False, "message": "surge", "surge": True}
        discarded = random.choice(list(inv.hand))
        inv.hand.remove(discarded)
        inv.discard.append(discarded)
        cd = game.state.get_card_data(discarded)
        x = (cd.cost or 0) if cd is not None else 0
        log(f"🧠 遭遇：魂牵梦绕——随机弃掉【{game.state.card_name(discarded)}】，意志{x}，失败失去1行动")

        def on_fail(_r):
            if inv.actions_remaining > 0:
                inv.actions_remaining -= 1
                log("  → 失去1行动")
        run_test(investigator_id, skill=Skill.WILLPOWER, difficulty=x, on_failure=on_fail)
        return {"pending": False, "message": "psychic_pull"}

    # ---- Agents of Hydra / Deep Ones ----
    if card_id == "deep_one_assault":
        loc = game.state.get_location(inv.location_id)
        # 1) 与你所在地点的每个深潜者解除交战（交战的敌人视为在你地点）
        for iid in list(inv.threat_area):
            if _has_tag(_tags_of(game, iid), "deep_one"):
                inv.threat_area.remove(iid)
                if loc is not None and iid not in loc.enemies:
                    loc.enemies.append(iid)
        # 2) 你所在地与连接地点的每个深潜者与你交战
        area = [inv.location_id] + list(loc.connections if loc is not None else [])
        engaged = 0
        for lid in area:
            l = game.state.get_location(lid)
            if l is None:
                continue
            for iid in list(l.enemies):
                if _has_tag(_tags_of(game, iid), "deep_one"):
                    l.enemies.remove(iid)
                    if iid not in inv.threat_area:
                        inv.threat_area.append(iid)
                    engaged += 1
        if engaged == 0:
            pulled = _pull_enemy_by_tag(game, "deep_one")
            if pulled:
                controller._spawn_enemy_from_encounter(pulled, investigator_id)
                random.shuffle(game.state.scenario.encounter_deck)
                log(f"🌊 遭遇：深潜者来袭——无深潜者可交战，抽到【{game.state.card_name(pulled)}】并与你交战")
            else:
                log("🌊 遭遇：深潜者来袭——遭遇牌堆/弃牌堆中无深潜者敌人")
        else:
            log(f"🌊 遭遇：深潜者来袭——{engaged}个深潜者敌人与你交战")
        return {"pending": False, "message": "deep_one_assault"}

    if card_id == "undertow":
        if not _is_flooded(game, inv.location_id):
            log("🌊 遭遇：暗流涌动——所在地点未淹没，涌动")
            return {"pending": False, "message": "surge", "surge": True}
        _place_in_threat(game, inv, "undertow")

        holder: list[Any] = []

        def _on_move(ctx):
            if ctx.investigator_id != investigator_id:
                return
            iid = _threat_copy(game, inv, "undertow")
            if iid is None:
                game.event_bus.unregister(holder[0])
                return
            game.event_bus.unregister(holder[0])
            _remove_from_threat(game, inv, iid)
            game.damage_engine.deal_damage(investigator_id, damage=2, horror=2)
            log("🌊 暗流涌动：你移动后受到2伤害2恐惧，弃掉暗流涌动")

        holder.append(game.event_bus.register(GameEvent.MOVE_ACTION_INITIATED, _on_move,
                                              priority=TimingPriority.AFTER))
        log("🌊 遭遇：暗流涌动——放入威胁区（移动后受2伤害2恐惧并弃掉；"
            "可用 activate_fight_the_pull 弃1手牌检定格斗/敏捷3弃掉）")
        return {"pending": False, "message": "undertow"}

    if card_id == "rising_tides":
        target = _nearest_location(game, inv.location_id,
                                   lambda lid: _flood_level(game, lid) < 2)
        if target is None:
            log("🌊 遭遇：潮起——没有可提升淹没等级的地点，涌动")
            return {"pending": False, "message": "surge", "surge": True}
        _increase_flood(game, target)
        log(f"🌊 遭遇：潮起——提升【{target}】的淹没等级（现为{_flood_level(game, target)}）")
        return {"pending": False, "message": "rising_tides"}

    if card_id == "riptide":
        if not _is_flooded(game, inv.location_id):
            log("🌀 遭遇：激流——所在地点未淹没，涌动")
            return {"pending": False, "message": "surge", "surge": True}
        difficulty = 4 if _is_fully_flooded(game, inv.location_id) else 3
        log(f"🌀 遭遇：激流（敏捷{difficulty}，失败弃1支援，否则按差额失去资源）")

        def on_fail(r):
            # 简化：自动弃最便宜的支援（官方为选择并弃掉1个支援）
            cid = _discard_cheapest_asset(controller, inv)
            if cid is not None:
                log(f"  → 弃掉支援【{game.state.card_name(cid)}】")
                return
            m = _margin_fail(r)
            if m > 0:
                lost = min(m, inv.resources)
                inv.resources -= lost
                log(f"  → 无支援可弃，失去{lost}资源")
        run_test(investigator_id, skill=Skill.AGILITY, difficulty=difficulty, on_failure=on_fail)
        return {"pending": False, "message": "riptide"}

    # ---- The Lair of Dagon ----
    if card_id == "fog_over_innsmouth":
        # 简化：官方在成功后才二选一；此处检定期前先通过 pending_choice 确定
        if choice is None:
            svars["pending_choice"] = {
                "card_id": card_id,
                "investigator_id": investigator_id,
                "prompt": "印斯茅斯之雾：若检定成功——受1恐惧 或 将本卡放到密谋牌堆旁（失败则两者都执行）",
                "options": [
                    {"id": "take_horror", "label": "成功时：受到1恐惧"},
                    {"id": "put_in_play", "label": "成功时：放到密谋牌堆旁（每地点+1隐蔽）"},
                ],
            }
            return {"pending": True, "message": "pending_choice"}
        log("🌫️ 遭遇：印斯茅斯之雾（意志3）")

        def _put_in_play():
            _put_next_to_agenda(game, "fog_over_innsmouth")
            log("  → 放到密谋牌堆旁（每地点+1隐蔽[未强制，见 vars.next_to_agenda]；轮末弃1张）")

        def on_success(_r):
            if choice == "put_in_play":
                _put_in_play()
            else:
                game.damage_engine.deal_damage(investigator_id, horror=1)
                log("  → 成功：受1恐惧")

        def on_failure(_r):
            game.damage_engine.deal_damage(investigator_id, horror=1)
            _put_in_play()
            log("  → 失败：受1恐惧并放到密谋牌堆旁")

        _run_test_full(controller, investigator_id, skill=Skill.WILLPOWER,
                       difficulty=3, on_success=on_success, on_failure=on_failure)
        return {"pending": False, "message": "fog_over_innsmouth"}

    if card_id == "macabre_memento":
        log("💀 遭遇：死亡纪念（意志3，抽出异教徒自动失败；失败受2恐惧）")
        _watch_tokens(game, investigator_id, {ChaosTokenType.CULTIST},
                      on_reveal=lambda ctx: ctx.extra.__setitem__("force_auto_fail", True))
        run_test(investigator_id, skill=Skill.WILLPOWER, difficulty=3,
                 on_failure=lambda _r: game.damage_engine.deal_damage(investigator_id, horror=2))
        return {"pending": False, "message": "macabre_memento"}

    if card_id == "fractured_consciousness":
        log("🧩 遭遇：崩裂意识（智力3，抽出石板自动失败；失败受2伤害）")
        _watch_tokens(game, investigator_id, {ChaosTokenType.TABLET},
                      on_reveal=lambda ctx: ctx.extra.__setitem__("force_auto_fail", True))
        run_test(investigator_id, skill=Skill.INTELLECT, difficulty=3,
                 on_failure=lambda _r: game.damage_engine.deal_damage(investigator_id, damage=2))
        return {"pending": False, "message": "fractured_consciousness"}

    if card_id == "memory_of_oblivion":
        # 简化：意志/智力4 二选一固定取意志（官方由你选择）
        log("🕳️ 遭遇：湮灭记忆（意志4[简化：官方可改选智力4]，抽出旧神之物自动失败；"
            "失败按差额弃手牌）")
        _watch_tokens(game, investigator_id, {ChaosTokenType.ELDER_THING},
                      on_reveal=lambda ctx: ctx.extra.__setitem__("force_auto_fail", True))

        def on_fail(r):
            dropped = _discard_hand_cards(inv, _margin_fail(r))
            if dropped:
                log(f"  → 弃掉手牌【{_log_names(game, dropped)}】")
        run_test(investigator_id, skill=Skill.WILLPOWER, difficulty=4, on_failure=on_fail)
        return {"pending": False, "message": "memory_of_oblivion"}

    if card_id == "malfunction":
        # 叠加到最近的载具剧情支援（支援位置按控制者所在地点计）
        dist = _bfs_distances(game, inv.location_id)
        best = None
        best_d = None
        for iid, inst in game.state.cards_in_play.items():
            cd = game.state.get_card_data(inst.card_id)
            if cd is None or cd.type.value != "asset":
                continue
            if not _card_has_tag(cd, "vehicle"):
                continue
            owner = game.state.get_investigator(inst.controller_id)
            loc_id = owner.location_id if owner is not None else inv.location_id
            d = dist.get(loc_id)
            if d is None:
                continue
            if best_d is None or d < best_d:
                best, best_d = iid, d
        if best is None:
            log("🔧 遭遇：机械故障——场上无载具支援，无效果")
            return {"pending": False, "message": "malfunction"}
        inst_id = game.state.next_instance_id()
        game.state.cards_in_play[inst_id] = CardInstance(
            instance_id=inst_id, card_id="malfunction",
            owner_id="scenario", controller_id="scenario", attached_to=best)
        svars.setdefault("malfunction", {})[inst_id] = best
        target_cd = game.state.get_card_data(game.state.get_card_instance(best).card_id)
        log(f"🔧 遭遇：机械故障——叠加到【{target_cd.name_cn if target_cd else best}】"
            f"（其[行动]能力不能触发[未强制]；可用 activate_fix_malfunction 智力3弃掉）")
        return {"pending": False, "message": "malfunction"}

    if card_id == "tidal_alignment":
        # Peril（不能投入卡牌——未强制）。简化：自动选择抽卡调查员所在地点
        # （官方由你选择1个有调查员的地点）
        loc_id = inv.location_id
        increased = _increase_flood(game, loc_id)
        victims = [i for i in game.state.get_investigators_at_location(loc_id)
                   if not i.is_defeated]
        for v in victims:
            game.damage_engine.deal_damage(v.investigator_id, damage=1)
        log(f"🌊 遭遇：星潮合相——提升【{loc_id}】淹没等级，该地点{len(victims)}名调查员各受1伤害")
        if not increased:
            log("  → 淹没等级未提升，涌动")
            return {"pending": False, "message": "surge", "surge": True}
        return {"pending": False, "message": "tidal_alignment"}

    if card_id == "syzygy":
        # Peril（未强制）
        if choice is None:
            svars["pending_choice"] = {
                "card_id": card_id,
                "investigator_id": investigator_id,
                "prompt": "朔望：你必须决定——全体失去3资源 / 全体受2恐惧 / 当前密谋+1毁灭",
                "options": [
                    {"id": "lose_resources", "label": "每位调查员失去3资源"},
                    {"id": "take_horror", "label": "每位调查员受2恐惧"},
                    {"id": "place_doom", "label": "当前密谋+1毁灭（可能推进）"},
                ],
            }
            return {"pending": True, "message": "pending_choice"}
        if choice == "place_doom":
            game.state.scenario.doom_on_agenda += 1
            controller._check_agenda_threshold()
            log("🌑 遭遇：朔望——当前密谋+1毁灭")
        elif choice == "take_horror":
            for other_id in list(game.state.player_order):
                other = game.state.get_investigator(other_id)
                if other is not None and not other.is_defeated:
                    game.damage_engine.deal_damage(other_id, horror=2)
            log("🌑 遭遇：朔望——每位调查员受2恐惧")
        else:
            for other_id in list(game.state.player_order):
                other = game.state.get_investigator(other_id)
                if other is not None and not other.is_defeated:
                    other.resources = max(0, other.resources - 3)
            log("🌑 遭遇：朔望——每位调查员失去3资源")
        return {"pending": False, "message": "syzygy"}

    # ---- The Innsmouth Look / Furtive Locals ----
    if card_id == "innsmouth_look":
        if _threat_copy(game, inv, "innsmouth_look") is not None:
            log("🐟 遭遇：印斯茅斯面容——威胁区已有，无效果")
            return {"pending": False, "message": "innsmouth_look"}
        _place_in_threat(game, inv, "innsmouth_look")
        inv.sanity_bonus -= 1
        svars.setdefault("deep_one_trait", {})[investigator_id] = True
        holder: list[Any] = []

        def _on_value(ctx):
            if ctx.investigator_id != investigator_id:
                return
            if _threat_copy(game, inv, "innsmouth_look") is None:
                game.event_bus.unregister(holder[0])
                return
            if ctx.skill_type == Skill.INTELLECT:
                ctx.modify_amount(-1, "innsmouth_look")

        holder.append(game.event_bus.register(
            GameEvent.SKILL_VALUE_DETERMINED, _on_value, priority=TimingPriority.WHEN))
        log("🐟 遭遇：印斯茅斯面容——放入威胁区（-1智力/-1神智，获得深潜者属性[记入vars]；"
            "可用 activate_discard_innsmouth_look 意志3弃掉）")
        return {"pending": False, "message": "innsmouth_look"}

    if card_id == "furtive_locals":
        # 简化：官方在成功后才二选一；此处检定期前先通过 pending_choice 确定
        if choice is None:
            svars["pending_choice"] = {
                "card_id": card_id,
                "investigator_id": investigator_id,
                "prompt": "鬼祟的当地人：若检定成功——受1伤害 或 将本卡放到密谋牌堆旁（失败则两者都执行）",
                "options": [
                    {"id": "take_damage", "label": "成功时：受到1伤害"},
                    {"id": "put_in_play", "label": "成功时：放到密谋牌堆旁（不能谈判）"},
                ],
            }
            return {"pending": True, "message": "pending_choice"}
        log("🕴️ 遭遇：鬼祟的当地人（智力3）")

        def _put_in_play():
            _put_next_to_agenda(game, "furtive_locals")
            log("  → 放到密谋牌堆旁（调查员不能谈判[未强制]；轮末弃1张）")

        def on_success(_r):
            if choice == "put_in_play":
                _put_in_play()
            else:
                game.damage_engine.deal_damage(investigator_id, damage=1)
                log("  → 成功：受1伤害")

        def on_failure(_r):
            game.damage_engine.deal_damage(investigator_id, damage=1)
            _put_in_play()
            log("  → 失败：受1伤害并放到密谋牌堆旁")

        _run_test_full(controller, investigator_id, skill=Skill.INTELLECT,
                       difficulty=3, on_success=on_success, on_failure=on_failure)
        return {"pending": False, "message": "furtive_locals"}

    # ---- Horror in High Gear ----
    if card_id == "deep_one_invasion":
        s = game.state.scenario
        s.encounter_deck.extend(s.encounter_discard)
        s.encounter_discard.clear()
        random.shuffle(s.encounter_deck)
        east = _east_locations(game, inv.location_id)
        spawned = []
        for lid in east:
            found = None
            while s.encounter_deck:
                cid = s.encounter_deck.pop(0)
                s.encounter_discard.append(cid)
                cd = game.state.get_card_data(cid)
                if cd is not None and cd.type.value == "enemy" \
                        and _card_has_tag(cd, "deep_one") and _card_has_tag(cd, "hunter"):
                    found = cid
                    break
            if found is None:
                break
            s.encounter_discard.remove(found)
            _spawn_enemy_at(game, found, lid)
            spawned.append((found, lid))
        if spawned:
            desc = "；".join(f"【{game.state.card_name(c)}】→{l}" for c, l in spawned)
            log(f"🌊 遭遇：深潜者入侵——混洗弃牌堆，{desc}")
        else:
            log("🌊 遭遇：深潜者入侵——混洗弃牌堆，未翻出带猎手的深潜者敌人")
        return {"pending": False, "message": "deep_one_invasion"}

    if card_id == "pulled_back":
        log("🪝 遭遇：拽回原处（意志3，失败移到东面连接地点并将钥匙放在地点上）")

        def on_fail(_r):
            east = _east_locations(game, inv.location_id)
            dest = east[0] if east else None
            if dest is not None:
                inv.location_id = dest  # 忽略屏障（引擎本就不拦截）
                log(f"  → 移到东面地点【{dest}】")
            else:
                log("  → 无东面地点，留在原地（简化：剧本网格未配置）")
            n = _place_keys_on_location(game, investigator_id, inv.location_id)
            if n:
                log(f"  → {n}个钥匙放在【{inv.location_id}】上")
        run_test(investigator_id, skill=Skill.WILLPOWER, difficulty=3, on_failure=on_fail)
        return {"pending": False, "message": "pulled_back"}

    if card_id == "inundated":
        loc = game.state.get_location(inv.location_id)
        placed = 0
        for conn in list(loc.connections if loc is not None else []):
            if _add_barrier(game, inv.location_id, conn):
                placed += 1
        if placed == 0:
            log("🌊 遭遇：泛滥——未放置任何屏障，涌动")
            return {"pending": False, "message": "surge", "surge": True}
        log(f"🌊 遭遇：泛滥——在【{inv.location_id}】与{placed}个连接地点之间放置屏障")
        return {"pending": False, "message": "inundated"}

    # ---- Devil Reef ----
    if card_id == "shapes_in_the_water":
        bonus = 2 if _is_fully_flooded(game, inv.location_id) else (1 if _is_flooded(game, inv.location_id) else 0)
        difficulty = 2 + bonus
        log(f"🌊 遭遇：水中身影（意志{difficulty}，失败受2恐惧）")
        run_test(investigator_id, skill=Skill.WILLPOWER, difficulty=difficulty,
                 on_failure=lambda _r: game.damage_engine.deal_damage(investigator_id, horror=2))
        return {"pending": False, "message": "shapes_in_the_water"}

    if card_id == "aquatic_ambush":
        _put_next_to_agenda(game, "aquatic_ambush")
        log("🌊 遭遇：伏兵出水——放到密谋牌堆旁（攻击淹没地点敌人时多抽1标记"
            "[未强制，见 vars.next_to_agenda]；轮末弃1张）")
        return {"pending": False, "message": "aquatic_ambush"}

    if card_id == "horrors_from_the_deep":
        bonus = 2 if _is_fully_flooded(game, inv.location_id) else (1 if _is_flooded(game, inv.location_id) else 0)
        difficulty = 2 + bonus
        log(f"🦈 遭遇：深海恐惧（敏捷{difficulty}，失败受2伤害）")
        run_test(investigator_id, skill=Skill.AGILITY, difficulty=difficulty,
                 on_failure=lambda _r: game.damage_engine.deal_damage(investigator_id, damage=2))
        return {"pending": False, "message": "horrors_from_the_deep"}

    if card_id == "stowaway":
        riders = []
        for iid in list(game.state.player_order):
            other = game.state.get_investigator(iid)
            if other is None or other.is_defeated or not _in_vehicle(game, iid):
                continue
            riders.append(iid)
        if not riders:
            log("🚢 遭遇：偷偷上船——没有调查员在载具上，涌动")
            return {"pending": False, "message": "surge", "surge": True}
        # 简化：统一选择受1伤害1恐惧（官方为 受1伤害1恐惧 或 离开载具 各自二选一，
        # 且离开者本轮不能再进入——引擎无载具动作，记 vars 即可）
        for iid in riders:
            game.damage_engine.deal_damage(iid, damage=1, horror=1)
        log(f"🚢 遭遇：偷偷上船——载具上的{len(riders)}名调查员各受1伤害1恐惧（简化：未选离开载具）")
        return {"pending": False, "message": "stowaway"}

    if card_id == "dragged_under":
        _place_in_threat(game, inv, "dragged_under")
        if _in_vehicle(game, investigator_id):
            _leave_vehicle(game, investigator_id)
            log("🌊 拖入水底：你离开载具")
        svars.setdefault("cannot_enter_vehicles", {})[investigator_id] = True
        log("🌊 遭遇：拖入水底——放入威胁区（不能进入载具[记入vars]；"
            "可用 activate_discard_dragged_under 格斗/敏捷3弃掉）")
        return {"pending": False, "message": "dragged_under"}

    # ---- Horror in High Gear（载具 Hazard）----
    if card_id == "bumpy_ride":
        if not _in_vehicle(game, investigator_id):
            log("🚗 遭遇：颠簸前行——不在载具上（敏捷5，失败受3伤害）")
            run_test(investigator_id, skill=Skill.AGILITY, difficulty=5,
                     on_failure=lambda _r: game.damage_engine.deal_damage(investigator_id, damage=3))
            return {"pending": False, "message": "bumpy_ride"}
        driver_id = _vehicle_driver(game, investigator_id)
        mates = _vehicle_mates(game, investigator_id)
        log(f"🚗 遭遇：颠簸前行——司机【{driver_id}】敏捷3，失败载具内每人受2伤害")

        def on_fail(_r):
            for iid in mates:
                game.damage_engine.deal_damage(iid, damage=2)
        run_test(driver_id, skill=Skill.AGILITY, difficulty=3, on_failure=on_fail)
        return {"pending": False, "message": "bumpy_ride"}

    if card_id == "i_cant_see":
        if not _in_vehicle(game, investigator_id):
            log("🙈 遭遇：我看不见了！——不在载具上（意志5，失败受3恐惧）")
            run_test(investigator_id, skill=Skill.WILLPOWER, difficulty=5,
                     on_failure=lambda _r: game.damage_engine.deal_damage(investigator_id, horror=3))
            return {"pending": False, "message": "i_cant_see"}
        driver_id = _vehicle_driver(game, investigator_id)
        mates = _vehicle_mates(game, investigator_id)
        log(f"🙈 遭遇：我看不见了！——司机【{driver_id}】意志3，失败载具内每人受2恐惧")

        def on_fail(_r):
            for iid in mates:
                game.damage_engine.deal_damage(iid, horror=2)
        run_test(driver_id, skill=Skill.WILLPOWER, difficulty=3, on_failure=on_fail)
        return {"pending": False, "message": "i_cant_see"}

    if card_id == "eyes_in_the_trees":
        log("🌲 遭遇：林中之眼（意志4，失败弃1支援或按差额弃手牌；载具内其他人同样结算）")

        def _penalty(target_id: str, margin: int) -> None:
            target = game.state.get_investigator(target_id)
            if target is None:
                return
            # 简化：有支援则自动弃最便宜支援，否则按差额弃手牌（官方二选一）
            cid = _discard_cheapest_asset(controller, target)
            if cid is not None:
                log(f"  → 【{target_id}】弃掉支援【{game.state.card_name(cid)}】")
                return
            dropped = _discard_hand_cards(target, margin)
            if dropped:
                log(f"  → 【{target_id}】弃掉手牌【{_log_names(game, dropped)}】")

        def on_fail(r):
            m = _margin_fail(r)
            _penalty(investigator_id, m)
            if _in_vehicle(game, investigator_id):
                # 简化：同载具其他调查员按相同差额结算（官方"如同其刚刚失败"）
                for iid in _vehicle_mates(game, investigator_id):
                    if iid != investigator_id:
                        _penalty(iid, m)
        run_test(investigator_id, skill=Skill.WILLPOWER, difficulty=4, on_failure=on_fail)
        return {"pending": False, "message": "eyes_in_the_trees"}

    if card_id == "theyre_catching_up":
        moved = 0
        for iid in list(game.state.cards_in_play.keys()):
            if not _has_tag(_tags_of(game, iid), "hunter"):
                continue
            cd = game.state.get_card_data(game.state.cards_in_play[iid].card_id)
            if cd is None or cd.type.value != "enemy":
                continue
            if _resolve_hunter_step(game, iid):
                moved += 1
        if moved > 0:
            log(f"🚗 遭遇：他们追上来了！——结算场上猎手，{moved}个敌人移动")
            return {"pending": False, "message": "theyre_catching_up"}
        s = game.state.scenario
        found = None
        while s.encounter_deck:
            cid = s.encounter_deck.pop(0)
            s.encounter_discard.append(cid)
            if _is_enemy_with_tag(game, cid, "vehicle"):
                found = cid
                break
        if found is None:
            log("🚗 遭遇：他们追上来了！——无敌人移动，遭遇牌堆中也没有载具敌人")
            return {"pending": False, "message": "theyre_catching_up"}
        s.encounter_discard.remove(found)
        dest = _rearmost_location(game, inv.location_id)
        _spawn_enemy_at(game, found, dest)
        log(f"🚗 遭遇：他们追上来了！——无敌人移动，【{game.state.card_name(found)}】生成在最后方地点【{dest}】")
        return {"pending": False, "message": "theyre_catching_up"}

    # ---- A Light in the Fog ----
    if card_id == "hideous_lullaby":
        deep_ones = _enemies_with_tag(game, "deep_one")
        if not deep_ones:
            log("🎵 遭遇：丑恶摇篮曲——场上无深潜者敌人，涌动")
            return {"pending": False, "message": "surge", "surge": True}
        x = 0
        for iid in deep_ones:
            inst = game.state.get_card_instance(iid)
            cd = game.state.get_card_data(inst.card_id) if inst else None
            x = max(x, (cd.enemy_fight or 0) if cd is not None else 0)
        log(f"🎵 遭遇：丑恶摇篮曲（意志{x}＝最高攻击值，失败受2恐惧）")
        run_test(investigator_id, skill=Skill.WILLPOWER, difficulty=x,
                 on_failure=lambda _r: game.damage_engine.deal_damage(investigator_id, horror=2))
        return {"pending": False, "message": "hideous_lullaby"}

    if card_id == "kiss_of_brine":
        difficulty = 4 if _is_flooded(game, inv.location_id) else 2
        log(f"🧂 遭遇：咸海之吻（格斗{difficulty}，失败受1伤害并放入威胁区）")

        def on_fail(_r):
            game.damage_engine.deal_damage(investigator_id, damage=1)
            _place_in_threat(game, inv, "kiss_of_brine")
            svars.setdefault("kiss_of_brine", {})[investigator_id] = True
            # 不能获得资源/抽卡：记入 vars，未强制（引擎无对应拦截钩子）

            def _on_enemy_phase_end(_ctx):
                iid = _threat_copy(game, inv, "kiss_of_brine")
                if iid is not None:
                    _remove_from_threat(game, inv, iid)
                svars.get("kiss_of_brine", {}).pop(investigator_id, None)
                log("🧂 咸海之吻：敌军阶段结束，弃掉")

            _register_one_shot(game, GameEvent.ENEMY_PHASE_ENDS, _on_enemy_phase_end)
        run_test(investigator_id, skill=Skill.COMBAT, difficulty=difficulty, on_failure=on_fail)
        return {"pending": False, "message": "kiss_of_brine"}

    if card_id == "totality":
        log("🌒 遭遇：全蚀（意志3，失败放入威胁区）")

        def on_fail(_r):
            _place_in_threat(game, inv, "totality")
            holders: list[Any] = []

            def _cleanup():
                for entry in holders:
                    game.event_bus.unregister(entry)

            def _on_move(ctx):
                if ctx.investigator_id != investigator_id:
                    return
                if _threat_copy(game, inv, "totality") is None:
                    _cleanup()
                    return
                moved = game.state.get_investigator(ctx.investigator_id)
                if moved is not None and _is_flooded(game, moved.location_id):
                    game.damage_engine.deal_damage(investigator_id, horror=1)
                    log("🌒 全蚀：你进入淹没地点，受1恐惧")

            def _on_turn_end(ctx):
                if ctx.investigator_id != investigator_id:
                    return
                _cleanup()
                iid = _threat_copy(game, inv, "totality")
                if iid is not None:
                    _remove_from_threat(game, inv, iid)
                log("🌒 全蚀：你的回合结束，弃掉")

            holders.append(game.event_bus.register(
                GameEvent.MOVE_ACTION_INITIATED, _on_move, priority=TimingPriority.AFTER))
            holders.append(game.event_bus.register(
                GameEvent.INVESTIGATOR_TURN_ENDS, _on_turn_end, priority=TimingPriority.AFTER))
        run_test(investigator_id, skill=Skill.WILLPOWER, difficulty=3, on_failure=on_fail)
        return {"pending": False, "message": "totality"}

    if card_id == "worth_his_salt":
        # 引擎缺口：即便在胜利牌区也能叠加、猎手再触发、攻击+1/+1 均无钩子，
        # 统一记入 vars（key 为 Oceiros 的 instance_id、"victory" 或 "absent"）。
        target = None
        for iid, inst in game.state.cards_in_play.items():
            if inst.card_id == "oceiros_marsh":
                target = iid
                break
        if target is not None:
            where = target
        elif "oceiros_marsh" in game.state.scenario.victory_display:
            where = "victory"
        else:
            where = "absent"
        svars["worth_his_salt"] = where
        log(f"🧂 遭遇：进腥尽力——叠加到奥赛罗思·马什（{where}；猎手再触发/攻击+1伤害+1恐惧"
            "[均未强制，记入 vars.worth_his_salt]）")
        return {"pending": False, "message": "worth_his_salt"}

    if card_id == "taken_captive":
        log("⛓️ 遭遇：惨遭俘虏（敏捷4，失败被俘虏，钥匙放到拘禁室）")

        def on_fail(_r):
            svars.setdefault("captured", {})[investigator_id] = True
            n = _place_keys_on_location(game, investigator_id, HOLDING_CELLS)
            log(f"  → 你被俘虏（记入 vars.captured），{n}个钥匙放到拘禁室"
                "（俘虏机制未实现，引擎缺口）")
        run_test(investigator_id, skill=Skill.AGILITY, difficulty=4, on_failure=on_fail)
        return {"pending": False, "message": "taken_captive"}

    # ---- Into the Maelstrom ----
    if card_id == "fulfill_the_oaths":
        act = min(3, game.state.scenario.current_act_index + 1)
        tests = [(Skill.AGILITY, 3)]
        if act >= 2:
            tests.append((Skill.COMBAT, 2))
        if act >= 3:
            tests.append((Skill.INTELLECT, 2))
        log(f"🌀 遭遇：践行誓约——场景{act}，依次检定"
            f"{' → '.join(f'{s.value}{d}' for s, d in tests)}，每次失败受1伤害")

        def _chain(idx: int) -> None:
            if idx >= len(tests):
                return
            skill, diff = tests[idx]

            def _after(_r):
                _chain(idx + 1)

            def _fail(r):
                game.damage_engine.deal_damage(investigator_id, damage=1)
                _after(r)

            _run_test_full(controller, investigator_id, skill=skill, difficulty=diff,
                           on_success=_after, on_failure=_fail)

        _chain(0)
        return {"pending": False, "message": "fulfill_the_oaths"}

    if card_id == "secret_gathering":
        game.chaos_bag.add_token(ChaosTokenType.CURSE)
        log("🕯️ 遭遇：秘密集会——混乱袋+1诅咒（意志4，失败：每个异教徒敌人+1毁灭并受1恐惧，"
            "抽出诅咒则2恐惧）")
        watch = _watch_tokens(game, investigator_id, {ChaosTokenType.CURSE})

        def on_fail(_r):
            cultists = _enemies_with_tag(game, "cultist")
            for iid in cultists:
                inst = game.state.get_card_instance(iid)
                if inst is not None:
                    inst.doom = (inst.doom or 0) + 1
            if cultists:
                controller._check_agenda_threshold()
            horror = 2 if watch["count"] > 0 else 1
            game.damage_engine.deal_damage(investigator_id, horror=horror)
            log(f"  → {len(cultists)}个异教徒敌人各+1毁灭，受{horror}恐惧")
        run_test(investigator_id, skill=Skill.WILLPOWER, difficulty=4, on_failure=on_fail)
        return {"pending": False, "message": "secret_gathering"}

    if card_id == "esoteric_ritual":
        log("🕯️ 遭遇：玄密仪式（意志4，失败弃2手牌或弃1支援，抽出诅咒则两者都执行）")
        watch = _watch_tokens(game, investigator_id, {ChaosTokenType.CURSE})

        def on_fail(_r):
            if watch["count"] > 0:
                dropped = _discard_hand_cards(inv, 2)
                cid = _discard_cheapest_asset(controller, inv)
                log(f"  → 抽出诅咒：弃手牌【{_log_names(game, dropped)}】"
                    + (f"并弃掉支援【{game.state.card_name(cid)}】" if cid else ""))
                return
            # 简化：手牌≥2则弃前2张，否则弃最便宜支援（官方二选一）
            if len(inv.hand) >= 2:
                dropped = _discard_hand_cards(inv, 2)
                log(f"  → 弃掉手牌【{_log_names(game, dropped)}】")
            else:
                cid = _discard_cheapest_asset(controller, inv)
                if cid is not None:
                    log(f"  → 弃掉支援【{game.state.card_name(cid)}】")
        run_test(investigator_id, skill=Skill.WILLPOWER, difficulty=4, on_failure=on_fail)
        return {"pending": False, "message": "esoteric_ritual"}

    if card_id == "heralds_of_the_deep":
        difficulty = 5 if _is_flooded(game, inv.location_id) else 3
        log(f"🌊 遭遇：深海兆使（意志{difficulty}，失败按差额向混乱袋加诅咒）")
        result: dict[str, Any] = {"pending": False, "message": "heralds_of_the_deep"}

        def on_fail(r):
            m = _margin_fail(r)
            current = sum(1 for t in game.chaos_bag.tokens
                          if t in (ChaosTokenType.BLESS, ChaosTokenType.CURSE))
            capacity = max(0, _BLESS_CURSE_CAP - current)
            added = min(m, capacity)
            for _ in range(added):
                game.chaos_bag.add_token(ChaosTokenType.CURSE)
            log(f"  → 混乱袋+{added}诅咒")
            if added < m:
                result["surge"] = True
                result["message"] = "surge"
                log("  → 无法加足诅咒标记，涌动")
        run_test(investigator_id, skill=Skill.WILLPOWER, difficulty=difficulty, on_failure=on_fail)
        return result

    if card_id == "stone_barrier":
        target = _nearest_location(
            game, inv.location_id,
            lambda lid: controller.location_attachment_instance(lid, "stone_barrier") is None)
        if target is None:
            log("🪨 遭遇：石障——没有可叠加的地点，无效果")
            return {"pending": False, "message": "stone_barrier"}
        controller.attach_card_to_location("stone_barrier", target)
        surge = _is_flooded(game, target)
        log(f"🪨 遭遇：石障——叠加到【{target}】（准备时不能移出[未强制]；"
            f"可用 activate_exhaust_stone_barrier 敏捷1/格斗2/智力3 消耗它）"
            + ("，该地点已淹没，涌动" if surge else ""))
        out: dict[str, Any] = {"pending": False, "message": "stone_barrier"}
        if surge:
            out["surge"] = True
        return out

    if card_id == "treacherous_depths":
        # Peril（未强制）
        if choice is None:
            svars["pending_choice"] = {
                "card_id": card_id,
                "investigator_id": investigator_id,
                "prompt": "危险深渊：你必须——提升当前地点淹没等级 或 弃掉费用合计≥地点隐藏值的支援",
                "options": [
                    {"id": "increase_flood", "label": "提升你当前地点的淹没等级"},
                    {"id": "discard_assets", "label": "弃掉费用合计≥隐藏值的支援"},
                ],
            }
            return {"pending": True, "message": "pending_choice"}
        loc = game.state.get_location(inv.location_id)
        x = (loc.shroud or 0) + controller.location_shroud_bonus(inv.location_id)
        if choice == "discard_assets":
            # 先确认游戏区域支援费用合计足够再弃（官方只能选择可执行的项）
            total_available = 0
            for iid in inv.play_area:
                inst = game.state.get_card_instance(iid)
                cd = game.state.get_card_data(inst.card_id) if inst else None
                if cd is not None and cd.type.value == "asset":
                    total_available += cd.cost or 0
            if total_available >= x:
                discarded = _auto_discard_play_assets(controller, inv, x)
                log(f"🕳️ 遭遇：危险深渊——弃掉支援【{_log_names(game, discarded)}】（费用合计≥{x}）")
                return {"pending": False, "message": "treacherous_depths"}
            # 支援费用不足：回退到提升淹没等级
            log("🕳️ 遭遇：危险深渊——支援费用不足，改为提升淹没等级")
        _increase_flood(game, inv.location_id)
        log(f"🕳️ 遭遇：危险深渊——提升【{inv.location_id}】淹没等级（现为{_flood_level(game, inv.location_id)}）")
        return {"pending": False, "message": "treacherous_depths"}

    if card_id == "conspiracy_of_deep_ones":
        # Peril（未强制）
        sanctum_keys = 0
        for loc in game.state.locations.values():
            cd = loc.card_data
            traits = [_norm(t) for t in (getattr(cd, "traits", None) or [])]
            if "sanctum" in traits and _location_has_key(game, loc.location_id):
                sanctum_keys += 1
        difficulty = 2 + sanctum_keys
        log(f"🐙 遭遇：深潜者暗潮（意志{difficulty}＝2+带钥匙圣堂×{sanctum_keys}，"
            "失败：密谋+1毁灭 或 最近古神敌人攻击你）")

        def on_fail(_r):
            ancient_ones = _enemies_with_tag(game, "ancient_one")
            # 简化：场上有古神敌人时自动选择被攻击（避免推进密谋），否则放毁灭
            if ancient_ones:
                dist = _bfs_distances(game, inv.location_id)
                best = min(
                    ancient_ones,
                    key=lambda iid: dist.get(_enemy_location(game, iid) or "", 99))
                _enemy_attack(game, best, investigator_id)
                log(f"  → 最近的古神敌人【{game.state.card_name(game.state.get_card_instance(best).card_id)}】攻击你")
            else:
                game.state.scenario.doom_on_agenda += 1
                controller._check_agenda_threshold()
                log("  → 场上无古神敌人，当前密谋+1毁灭")
        run_test(investigator_id, skill=Skill.WILLPOWER, difficulty=difficulty, on_failure=on_fail)
        return {"pending": False, "message": "conspiracy_of_deep_ones"}

    if card_id == "thalassophobia":
        affected = []
        for other_id in list(game.state.player_order):
            other = game.state.get_investigator(other_id)
            if other is None or other.is_defeated:
                continue
            level = _flood_level(game, other.location_id)
            if level >= 2:
                game.damage_engine.deal_damage(other_id, horror=1, direct=True)
                affected.append((other_id, "直接恐惧"))
            elif level == 1:
                game.damage_engine.deal_damage(other_id, horror=1)
                affected.append((other_id, "恐惧"))
        if not affected:
            log("🌊 遭遇：深海恐惧症——没有调查员在淹没地点，涌动")
            return {"pending": False, "message": "surge", "surge": True}
        desc = "、".join(f"【{iid}】1{k}" for iid, k in affected)
        log(f"🌊 遭遇：深海恐惧症——{desc}")
        return {"pending": False, "message": "thalassophobia"}

    return None


# ---------------------------------------------------------------------------
# 公开激活方法（持续卡的 [行动]/[快速] 能力；供 session 层/测试调用）
# ---------------------------------------------------------------------------

def activate_fight_the_pull(controller, investigator_id: str, skill: str = "combat") -> bool:
    """[快速] 弃1张手牌：检定格斗(3)或敏捷(3)挣脱暗流涌动，成功则弃掉。"""
    game = controller.game
    inv = game.state.get_investigator(investigator_id)
    if inv is None or not inv.hand:
        return False
    iid = _threat_copy(game, inv, "undertow")
    if iid is None:
        return False
    cost = inv.hand.pop(0)  # 简化：自动弃第1张（官方由你选择）
    inv.discard.append(cost)
    sk = Skill.AGILITY if skill == "agility" else Skill.COMBAT

    def _ok(_r):
        _remove_from_threat(game, inv, iid)
        controller.log("🌊 挣脱潮水：检定成功，弃掉【暗流涌动】")

    game.skill_test_engine.run_test(
        investigator_id=investigator_id, skill_type=sk, difficulty=3,
        committed_card_ids=[], on_success=_ok, on_failure=lambda r: None)
    return True


def activate_fix_malfunction(controller, investigator_id: str,
                             instance_id: str | None = None) -> bool:
    """[行动] 检定智力(3)修理机械故障，成功则弃掉。"""
    game = controller.game
    inv = game.state.get_investigator(investigator_id)
    if inv is None or inv.actions_remaining < 1:
        return False
    records = game.state.scenario.vars.get("malfunction", {})
    iid = instance_id or (next(iter(records), None))
    if iid is None or iid not in records:
        return False
    inst = game.state.get_card_instance(iid)
    if inst is None or inst.card_id != "malfunction":
        return False
    inv.actions_remaining -= 1

    def _ok(_r):
        records.pop(iid, None)
        game.state.cards_in_play.pop(iid, None)
        game.state.scenario.encounter_discard.append("malfunction")
        controller.log("🔧 修理成功，弃掉【机械故障】")

    game.skill_test_engine.run_test(
        investigator_id=investigator_id, skill_type=Skill.INTELLECT, difficulty=3,
        committed_card_ids=[], on_success=_ok, on_failure=lambda r: None)
    return True


def activate_discard_innsmouth_look(controller, investigator_id: str) -> bool:
    """[行动] 检定意志(3)，成功则弃掉印斯茅斯面容。"""
    game = controller.game
    inv = game.state.get_investigator(investigator_id)
    if inv is None or inv.actions_remaining < 1:
        return False
    iid = _threat_copy(game, inv, "innsmouth_look")
    if iid is None:
        return False
    inv.actions_remaining -= 1

    def _ok(_r):
        _remove_from_threat(game, inv, iid)
        inv.sanity_bonus += 1
        game.state.scenario.vars.get("deep_one_trait", {}).pop(investigator_id, None)
        controller.log("🐟 意志检定成功，弃掉【印斯茅斯面容】")

    game.skill_test_engine.run_test(
        investigator_id=investigator_id, skill_type=Skill.WILLPOWER, difficulty=3,
        committed_card_ids=[], on_success=_ok, on_failure=lambda r: None)
    return True


def activate_discard_dragged_under(controller, investigator_id: str,
                                   skill: str = "combat") -> bool:
    """[行动] 检定格斗(3)或敏捷(3)，成功则弃掉拖入水底。"""
    game = controller.game
    inv = game.state.get_investigator(investigator_id)
    if inv is None or inv.actions_remaining < 1:
        return False
    iid = _threat_copy(game, inv, "dragged_under")
    if iid is None:
        return False
    inv.actions_remaining -= 1
    sk = Skill.AGILITY if skill == "agility" else Skill.COMBAT

    def _ok(_r):
        _remove_from_threat(game, inv, iid)
        game.state.scenario.vars.get("cannot_enter_vehicles", {}).pop(investigator_id, None)
        controller.log("🌊 检定成功，弃掉【拖入水底】")

    game.skill_test_engine.run_test(
        investigator_id=investigator_id, skill_type=sk, difficulty=3,
        committed_card_ids=[], on_success=_ok, on_failure=lambda r: None)
    return True


def activate_exhaust_stone_barrier(controller, investigator_id: str,
                                   skill: str = "agility") -> bool:
    """[行动] 检定敏捷(1)/格斗(2)/智力(3)，成功则消耗同地点的石障。"""
    game = controller.game
    inv = game.state.get_investigator(investigator_id)
    if inv is None or inv.actions_remaining < 1:
        return False
    iid = controller.location_attachment_instance(inv.location_id, "stone_barrier")
    if iid is None:
        return False
    inv.actions_remaining -= 1
    skill_map = {"agility": (Skill.AGILITY, 1), "combat": (Skill.COMBAT, 2),
                 "intellect": (Skill.INTELLECT, 3)}
    sk, diff = skill_map.get(skill, skill_map["agility"])

    def _ok(_r):
        inst = game.state.get_card_instance(iid)
        if inst is not None:
            inst.exhausted = True
        controller.log("🪨 检定成功，消耗【石障】")

    game.skill_test_engine.run_test(
        investigator_id=investigator_id, skill_type=sk, difficulty=diff,
        committed_card_ids=[], on_success=_ok, on_failure=lambda r: None)
    return True
