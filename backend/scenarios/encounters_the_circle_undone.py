"""The Circle Undone encounter treachery resolution.

Called from ScenarioController.resolve_encounter_card as a fallback after the
Dunwich branch (wiring lives in official_core.py). Each handler returns a
result dict or None (to continue to the next matcher). Choice cards set
`scenario.vars["pending_choice"]` (with an "investigator_id" field for
multiplayer routing) and are re-entered with `choice=<option_id>`.

Cycle-specific reprints handled elsewhere (NOT here): eager_for_death and
psychopomps_song are Dunwich-era ids already resolved by
dunwich_encounters.resolve_dunwich_treachery.

Simplifications (documented per card below):

- Haunted abilities (闹鬼): the engine has no haunted system. The scenario
  layer injects `scenario.vars["haunted"] = {location_id: [{"type":
  "horror"|"damage", "amount": N}, ...]}`; `_resolve_haunted` resolves them
  against the triggering investigator. While whispers_in_the_dark is active,
  every location additionally gains "Haunted - Take 1 horror".
- Breaches (裂口): tracked in `scenario.vars["breaches"] = {location_id: N}`.
  Blank-text-box / incursion side effects are not enforced by the engine.
- Keys (钥匙): `scenario.vars["keys"] = {investigator_id: ["skull", ...]}`
  is injected by the scenario layer; keys moved onto enemies live in
  `scenario.vars["enemy_keys"] = {instance_id: [...]}`.
- Spectral encounter deck (幽灵遭遇牌堆): `scenario.vars
  ["spectral_encounter_deck"]` (top = index 0) / "spectral_encounter_discard".
  `scenario.vars["drawing_from_spectral"] = True` tells grave_light it was
  drawn from the spectral deck.
- Unfinished Business (未了之事): not present in card data; threat-area copies
  are matched by card_id prefix "unfinished_business". Triggering/flipping is
  recorded in vars ("unfinished_business_triggered" / "..._flipped"); the
  actual forced ability / Heretic flip is the scenario layer's responsibility.
- Peril cards: resolved openly; the no-consultation rule is a tabletop
  concern and not enforced.
- "You must either X or Y" failure effects auto-pick the most common branch
  (documented per card); only revelation-time choices use pending_choice.
- Ongoing threat-area restrictions (wracked skill penalty, bedeviled action
  lock, death_approaches +2 horror) are recorded in `scenario.vars` and NOT
  enforced (no hook points; e.g. HORROR_ASSIGNED only honors reductions).
- Hex [action] discard abilities are exposed as `activate_discard_hex`;
  primordial_gateway as `activate_close_gateway`; the "encounter deck runs
  out" forced triggers as `notify_encounter_deck_empty` (engine gap: no such
  event exists).
- Tests inside event handlers / activations call skill_test_engine.run_test
  directly (controller._run_skill_test exposes no success callback), matching
  the carcosa_encounters precedent.
"""

from __future__ import annotations

import random
from typing import Any

from backend.models.enums import GameEvent, Skill, TimingPriority
from backend.models.state import CardInstance, is_weakness_card

# Hex 诡计：[行动] 意志3 弃掉（同地点有消耗状态女巫敌人则自动成功）
_HEX_CARDS = ("wracked", "bedeviled", "pulled_by_the_stars", "punishment")

# 骷髅/异教徒/石板/古神 钥匙（for the greater good 机制）
_KEY_NAMES = ("skull", "cultist", "tablet", "elder_thing")


# ---------------------------------------------------------------------------
# 通用辅助（对齐 carcosa_encounters；TCU 数据 traits 为英文、keywords 为空，
# 因此标签判断同时扫描 keywords 与 traits）
# ---------------------------------------------------------------------------

def _margin_fail(result) -> int:
    return max(0, (getattr(result, "difficulty", 0) or 0) - (getattr(result, "modified_skill", 0) or 0))


def _log_names(game, cids: list[str]) -> str:
    return "、".join(game.state.card_name(c) for c in cids)


def _tags_of(game, instance_id: str) -> list[str]:
    inst = game.state.get_card_instance(instance_id)
    if inst is None:
        return []
    cd = game.state.get_card_data(inst.card_id)
    if cd is None:
        return []
    return list(getattr(cd, "keywords", None) or []) + list(getattr(cd, "traits", None) or [])


def _card_tags(game, card_id: str) -> list[str]:
    cd = game.state.get_card_data(card_id)
    if cd is None:
        return []
    return list(getattr(cd, "keywords", None) or []) + list(getattr(cd, "traits", None) or [])


def _is_enemy_with_tag(game, card_id: str, tag: str) -> bool:
    cd = game.state.get_card_data(card_id)
    if cd is None or cd.type.value != "enemy":
        return False
    return tag in _card_tags(game, card_id)


def _enemies_with_tag(game, tag: str) -> list[str]:
    out = []
    for iid, inst in game.state.cards_in_play.items():
        cd = game.state.get_card_data(inst.card_id)
        if cd is None or cd.type.value != "enemy":
            continue
        if tag in _tags_of(game, iid):
            out.append(iid)
    return out


def _nearest_enemy_with_tag(game, inv, tag: str) -> str | None:
    """最近的带标签敌人（交战 > 同地点 > 任意）。"""
    for iid in inv.threat_area:
        if tag in _tags_of(game, iid):
            return iid
    loc = game.state.get_location(inv.location_id)
    if loc:
        for iid in loc.enemies:
            if tag in _tags_of(game, iid):
                return iid
    for iid in _enemies_with_tag(game, tag):
        return iid
    return None


def _find_in_play(game, card_id: str) -> str | None:
    for iid, inst in game.state.cards_in_play.items():
        if inst.card_id == card_id:
            return iid
    return None


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


def _remove_from_threat(game, inv, instance_id: str) -> None:
    inst = game.state.cards_in_play.pop(instance_id, None)
    if inst is not None and instance_id in inv.threat_area:
        inv.threat_area.remove(instance_id)


def _discard_threat_copy(game, inv, card_id: str) -> bool:
    """Discard a threat-area treachery to the encounter discard; pop vars record."""
    iid = _threat_copy(game, inv, card_id)
    if iid is None:
        return False
    _remove_from_threat(game, inv, iid)
    game.state.scenario.encounter_discard.append(card_id)
    rec = game.state.scenario.vars.get(card_id)
    if isinstance(rec, dict):
        rec.pop(inv.investigator_id, None)
    return True


def _enemy_location(game, instance_id: str) -> str | None:
    for loc in game.state.locations.values():
        if instance_id in loc.enemies:
            return loc.location_id
    for inv in game.state.investigators.values():
        if instance_id in inv.threat_area:
            return inv.location_id
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


def _move_enemy_to_location(game, instance_id: str, location_id: str) -> None:
    """Move enemy to a location without engaging (hunter-style)."""
    for loc in game.state.locations.values():
        if instance_id in loc.enemies:
            loc.enemies.remove(instance_id)
    for other in game.state.investigators.values():
        if instance_id in other.threat_area:
            other.threat_area.remove(instance_id)
    loc = game.state.get_location(location_id)
    if loc is not None and instance_id not in loc.enemies:
        loc.enemies.append(instance_id)


def _enemy_attack(game, instance_id: str, investigator_id: str) -> None:
    inst = game.state.get_card_instance(instance_id)
    cd = game.state.get_card_data(inst.card_id) if inst else None
    if cd is None:
        return
    game.damage_engine.deal_damage(
        investigator_id, damage=cd.enemy_damage or 0,
        horror=cd.enemy_horror or 0, source=instance_id)


def _spawn_at_location(game, card_id: str, location_id: str) -> str:
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


def _spawn_engaged(game, card_id: str, inv) -> str:
    inst_id = game.state.next_instance_id()
    ci = CardInstance(
        instance_id=inst_id, card_id=card_id,
        owner_id="scenario", controller_id="scenario",
    )
    game.state.cards_in_play[inst_id] = ci
    inv.threat_area.append(inst_id)
    return inst_id


def _pull_card_from_encounter(game, card_id: str) -> str | None:
    """Search encounter deck then discard for a specific card id."""
    s = game.state.scenario
    for pile in (s.encounter_deck, s.encounter_discard):
        if card_id in pile:
            pile.remove(card_id)
            return card_id
    return None


def _register_one_shot(game, event: GameEvent, handler) -> None:
    """Register an event handler that unregisters itself after firing once."""
    holder: list[Any] = []

    def _wrap(ctx):
        entry = holder[0]
        game.event_bus.unregister(entry)
        handler(ctx)

    holder.append(game.event_bus.register(event, _wrap, priority=TimingPriority.AFTER))


def _threat_gone(game, inv, card_id: str, investigator_id: str) -> bool:
    rec = game.state.scenario.vars.get(card_id)
    return (not isinstance(rec, dict)
            or rec.get(investigator_id) is None
            or _threat_copy(game, inv, card_id) is None)


# ---------------------------------------------------------------------------
# 循环机制状态（引擎缺口，统一走 scenario.vars）
# ---------------------------------------------------------------------------

def _breaches(game) -> dict[str, int]:
    return game.state.scenario.vars.setdefault("breaches", {})


def _breach_count(game, location_id: str) -> int:
    return int(_breaches(game).get(location_id, 0))


def _add_breaches(game, location_id: str, n: int) -> None:
    b = _breaches(game)
    b[location_id] = int(b.get(location_id, 0)) + n


def _keys_of(game, investigator_id: str) -> list[str]:
    return list(game.state.scenario.vars.get("keys", {}).get(investigator_id, []))


def _resolve_haunted(controller, location_id: str, investigator_id: str) -> int:
    """Resolve each haunted ability on a location (engine gap: no haunted
    system — abilities are injected via scenario.vars["haunted"]). While
    whispers_in_the_dark is active, every location gains an extra
    "Haunted - Take 1 horror". Returns the number of abilities resolved."""
    game = controller.game
    svars = game.state.scenario.vars
    effects = list(svars.get("haunted", {}).get(location_id, []))
    if svars.get("whispers_in_the_dark"):
        effects.append({"type": "horror", "amount": 1})
    for eff in effects:
        amount = int(eff.get("amount", 1) or 1)
        if eff.get("type") == "damage":
            game.damage_engine.deal_damage(investigator_id, damage=amount)
        else:
            game.damage_engine.deal_damage(investigator_id, horror=amount)
        controller.log(f"👻 闹鬼：结算 {eff.get('type', 'horror')}x{amount}")
    return len(effects)


def _exhausted_witch_at(game, location_id: str) -> bool:
    ids: list[str] = []
    loc = game.state.get_location(location_id)
    if loc is not None:
        ids += list(loc.enemies)
    for inv in game.state.investigators.values():
        if inv.location_id == location_id:
            ids += list(inv.threat_area)
    for iid in ids:
        inst = game.state.get_card_instance(iid)
        if inst is not None and inst.exhausted and "witch" in _tags_of(game, iid):
            return True
    return False


def _surge(message: str = "surge") -> dict:
    return {"pending": False, "message": message, "surge": True}


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

def resolve_treachery(controller, card_id: str, *, investigator_id: str,
                      choice: str | None = None) -> dict | None:
    """Resolve a Circle Undone treachery. Returns result dict, or None."""
    game = controller.game
    inv = game.state.get_investigator(investigator_id)
    if inv is None:
        return None
    log = controller.log
    run_test = controller._run_skill_test
    svars = game.state.scenario.vars

    # ---- The Witching Hour ----
    if card_id == "watchers_grasp":
        watcher = _find_in_play(game, "the_spectral_watcher")
        if watcher is None:
            log("👁️ 遭遇：看守人的攫噬——幽灵看守人不在场，无效果")
            return {"pending": False, "message": card_id}
        inst = game.state.get_card_instance(watcher)
        game.damage_engine.heal(target_instance_id=watcher, damage=3)
        inst.exhausted = False
        # 简化：直接移至调查员地点交战（官方逐地点移动，猎物-你 仅本轮结算相关）
        _engage_investigator(game, watcher, inv)
        _enemy_attack(game, watcher, investigator_id)
        log("👁️ 遭遇：看守人的攫噬——治疗3伤害、准备、与你交战并立即攻击")
        return {"pending": False, "message": card_id}

    if card_id == "daemonic_piping":
        piper = _find_in_play(game, "piper_of_azathoth")
        if piper is not None:
            loc_id = _enemy_location(game, piper)
            loc = game.state.get_location(loc_id) if loc_id else None
            affected = {loc_id} if loc_id else set()
            if loc is not None:
                affected |= set(loc.connections)
            for other_id in list(game.state.player_order):
                other = game.state.get_investigator(other_id)
                if other is not None and not other.is_defeated \
                        and other.location_id in affected:
                    game.damage_engine.deal_damage(other_id, horror=1)
            log("🎶 遭遇：魔鬼的笛声——吹笛手所在及连接地点的调查员各受1恐惧，涌动")
            return _surge()
        count = int(svars.get("daemonic_piping", 0)) + 1
        if count >= 3:
            svars["daemonic_piping"] = 0
            # 简化：猎物=抽牌调查员；先从遭遇牌堆/弃牌堆找，找不到则从场外直接生成
            pulled = _pull_card_from_encounter(game, "piper_of_azathoth")
            _spawn_engaged(game, pulled or "piper_of_azathoth", inv)
            log("🎶 遭遇：魔鬼的笛声——集齐3张，阿撒托斯的吹笛手生成并与你交战，涌动")
        else:
            svars["daemonic_piping"] = count
            log(f"🎶 遭遇：魔鬼的笛声——放在密谋旁（第{count}张），涌动")
        return _surge()

    # ---- At Death's Doorstep ----
    if card_id == "diabolic_voices":
        copies = sum(1 for c in game.state.scenario.encounter_discard
                     if c == "diabolic_voices")
        difficulty = 3 + copies
        log(f"😈 遭遇：恶魔之音（意志{difficulty}，失败按差额随机弃手牌，无法弃则受恐惧）")

        def on_fail(r):
            m = _margin_fail(r)
            n = min(m, len(inv.hand))
            for cid in random.sample(inv.hand, n):
                inv.hand.remove(cid)
                inv.discard.append(cid)
                log(f"  → 随机弃掉【{game.state.card_name(cid)}】")
            rest = m - n
            if rest > 0:
                # 简化：无法弃牌时自动选择受恐惧（官方 1恐惧 或 1伤害 逐张二选一）
                game.damage_engine.deal_damage(investigator_id, horror=rest)
        run_test(investigator_id, skill=Skill.WILLPOWER, difficulty=difficulty,
                 on_failure=on_fail)
        return {"pending": False, "message": card_id}

    if card_id in ("wracked", "bedeviled"):
        _place_in_threat(game, inv, card_id)
        svars.setdefault(card_id, {})[investigator_id] = True
        # 简化：崩毀離析的"每轮首次检定全技能-1"、苦痛折磨的"不能触发[行动]能力"
        # 记入 vars 但未强制（无通用技能修正/行动拦截钩子，引擎缺口）
        note = "每轮首次检定全技能-1[未强制]" if card_id == "wracked" \
            else "不能触发自己卡牌上的[行动]能力[未强制]"
        cn = "崩毁离析" if card_id == "wracked" else "苦痛折磨"
        log(f"🕸️ 遭遇：{cn}——放入威胁区（{note}；可用 activate_discard_hex 花1行动检定意志3弃掉）")
        return {"pending": False, "message": card_id}

    if card_id == "mysteries_of_the_lodge":
        target = _nearest_enemy_with_tag(game, inv, "cultist")
        if target is None:
            log("🕯️ 遭遇：秘社玄仪——场上无异教徒敌人，涌动")
            return _surge()
        inst = game.state.get_card_instance(target)
        inst.doom += 1
        # 简化：本轮攻击/躲避/谈判该敌人难度+2 记入 vars，未强制（无难度修正钩子）
        svars["mysteries_of_the_lodge"] = {
            "round": game.state.scenario.round_number, "target": target}
        controller._check_agenda_threshold()
        log(f"🕯️ 遭遇：秘社玄仪——【{game.state.card_name(inst.card_id)}】+1毁灭"
            "（本轮对其攻击/躲避/谈判难度+2[未强制]）")
        return {"pending": False, "message": card_id}

    if card_id == "evil_past":
        if _threat_copy(game, inv, "evil_past") is not None:
            log("🌑 遭遇：邪恶往昔——威胁区已有，弃掉并涌动")
            return _surge()
        _place_in_threat(game, inv, card_id)
        svars.setdefault(card_id, {})[investigator_id] = True
        log("🌑 遭遇：邪恶往昔——放入威胁区（遭遇牌堆耗尽时受2恐惧并检定意志3；"
            "由 notify_encounter_deck_empty 触发）")
        return {"pending": False, "message": card_id}

    if card_id == "centuries_of_secrets":
        log("📜 遭遇：百年秘事（意志5，失败按差额弃遭遇堆顶；弃到诅咒诡计则受直接伤害）")

        def on_fail(r):
            m = _margin_fail(r)
            s = game.state.scenario
            discarded = [s.encounter_deck.pop(0)
                         for _ in range(min(m, len(s.encounter_deck)))]
            s.encounter_discard.extend(discarded)
            cursed = any(
                (game.state.get_card_data(c) is not None
                 and game.state.get_card_data(c).type.value == "treachery"
                 and "curse" in _card_tags(game, c))
                for c in discarded)
            if cursed:
                game.damage_engine.deal_damage(investigator_id, damage=1, direct=True)
                for iid in list(inv.play_area):
                    tags = _tags_of(game, iid)
                    if "ally" in tags or "盟友" in tags:
                        game.damage_engine.deal_damage(
                            investigator_id, damage=1, direct=True, target_instance_id=iid)
                log("  → 弃到诅咒诡计：你和你的每个盟友支援各受1点直接伤害")
        run_test(investigator_id, skill=Skill.WILLPOWER, difficulty=5,
                 on_failure=on_fail)
        return {"pending": False, "message": card_id}

    if card_id == "whispers_in_the_dark":
        svars["whispers_in_the_dark"] = True

        def _clear(_ctx):
            game.state.scenario.vars.pop("whispers_in_the_dark", None)
            game.state.scenario.encounter_discard.append("whispers_in_the_dark")
            log("🌫️ 黑暗中的低语：本轮结束，弃掉")
        _register_one_shot(game, GameEvent.ROUND_ENDS, _clear)
        log("🌫️ 遭遇：黑暗中的低语——放在密谋旁（本轮每个地点获得“闹鬼-受1恐惧”，轮末弃掉）")
        return {"pending": False, "message": card_id}

    if card_id == "trapped_spirits":
        log("😱 遭遇：被困的灵魂（敏捷3，失败按差额受伤害；闹鬼地点投入额外费用[未强制]）")
        run_test(investigator_id, skill=Skill.AGILITY, difficulty=3,
                 on_failure=lambda r: game.damage_engine.deal_damage(
                     investigator_id, damage=_margin_fail(r)))
        return {"pending": False, "message": card_id}

    if card_id == "realm_of_torment":
        _place_in_threat(game, inv, card_id)
        svars.setdefault(card_id, {})[investigator_id] = True

        begins_holder: list[Any] = []
        ends_holder: list[Any] = []

        def _on_turn_begins(ctx):
            if ctx.investigator_id != investigator_id:
                return
            if _threat_gone(game, inv, card_id, investigator_id):
                game.event_bus.unregister(begins_holder[0])
                return
            _resolve_haunted(controller, inv.location_id, investigator_id)
            log("🌋 苦痛之地：回合开始，结算所在地点的闹鬼能力")

        def _on_turn_ends(ctx):
            if ctx.investigator_id != investigator_id:
                return
            if _threat_gone(game, inv, card_id, investigator_id):
                game.event_bus.unregister(ends_holder[0])
                return

            def _ok(_r):
                _discard_threat_copy(game, inv, card_id)
                log("🌋 苦痛之地：意志检定成功，弃掉")

            # _run_skill_test 不暴露成功回调，直接调用检定引擎
            game.skill_test_engine.run_test(
                investigator_id=investigator_id, skill_type=Skill.WILLPOWER,
                difficulty=3, committed_card_ids=[],
                on_success=_ok, on_failure=lambda r: None)

        begins_holder.append(game.event_bus.register(
            GameEvent.INVESTIGATOR_TURN_BEGINS, _on_turn_begins,
            priority=TimingPriority.AFTER))
        ends_holder.append(game.event_bus.register(
            GameEvent.INVESTIGATOR_TURN_ENDS, _on_turn_ends,
            priority=TimingPriority.AFTER))
        log("🌋 遭遇：苦痛之地——放入威胁区（回合开始结算闹鬼；回合结束意志3成功则弃掉）")
        return {"pending": False, "message": card_id}

    if card_id == "shapes_in_the_mist":
        _resolve_haunted(controller, inv.location_id, investigator_id)
        log("🌫️ 遭遇：雾中身形——结算所在地点的闹鬼能力，涌动")
        return _surge()

    if card_id == "terror_in_the_night":
        result = {"pending": False, "message": card_id}
        log("🌃 遭遇：恐怖夜色（意志4，失败放在密谋旁；失败3+涌动；集齐3张每人受3恐惧）")

        def on_fail(r):
            count = int(svars.get("terror_in_the_night", 0)) + 1
            if count >= 3:
                svars["terror_in_the_night"] = 0
                for other_id in list(game.state.player_order):
                    other = game.state.get_investigator(other_id)
                    if other is not None and not other.is_defeated:
                        game.damage_engine.deal_damage(other_id, horror=3)
                log("  → 集齐3张恐怖夜色：每位调查员受3恐惧")
            else:
                svars["terror_in_the_night"] = count
                log(f"  → 放在密谋旁（第{count}张）")
            if _margin_fail(r) >= 3:
                result["surge"] = True
                result["message"] = "surge"
        run_test(investigator_id, skill=Skill.WILLPOWER, difficulty=4,
                 on_failure=on_fail)
        return result

    if card_id == "fate_of_all_fools":
        # 场上其他副本（任意调查员威胁区）
        others: list[tuple[str, str]] = []
        for other_id in list(game.state.player_order):
            other = game.state.get_investigator(other_id)
            if other is None:
                continue
            for iid in other.threat_area:
                inst = game.state.get_card_instance(iid)
                if inst is not None and inst.card_id == card_id:
                    others.append((other_id, iid))
        if not others:
            _place_in_threat(game, inv, card_id)
            svars.setdefault(card_id, {})[investigator_id] = True
            log("🃏 遭遇：愚人的命运——放入你的威胁区")
            return {"pending": False, "message": card_id}
        # 简化：目标自动取玩家顺序中第一个带副本的调查员/副本（官方自选）
        if choice is None:
            svars["pending_choice"] = {
                "card_id": card_id,
                "investigator_id": investigator_id,
                "prompt": "愚人的命运：选择 持有者受2直接伤害 或 另一副本+1毁灭",
                "options": [
                    {"id": "take_direct", "label": "带愚人命运副本的调查员受2点直接伤害"},
                    {"id": "place_doom", "label": "在另一张愚人命运上放置1毁灭"},
                ],
            }
            return {"pending": True, "message": "pending_choice"}
        owner_id, other_iid = others[0]
        if choice == "place_doom":
            inst = game.state.get_card_instance(other_iid)
            inst.doom += 1
            controller._check_agenda_threshold()
            log("🃏 遭遇：愚人的命运——另一副本+1毁灭")
        else:
            game.damage_engine.deal_damage(owner_id, damage=2, direct=True)
            log(f"🃏 遭遇：愚人的命运——【{owner_id}】受2点直接伤害")
        return {"pending": False, "message": card_id}

    # ---- The Secret Name ----
    if card_id == "meddlesome_familiar":
        if _find_in_play(game, "brown_jenkin") is None:
            pulled = _pull_card_from_encounter(game, "brown_jenkin")
            if pulled:
                _spawn_at_location(game, pulled, inv.location_id)
                log(f"🐀 遭遇：好事魔宠——【{game.state.card_name(pulled)}】生成在你所在地点")
            else:
                log("🐀 遭遇：好事魔宠——遭遇牌堆/弃牌堆中未找到布朗·詹金")
            game.damage_engine.deal_damage(investigator_id, damage=1)
        else:
            pulled = _pull_card_from_encounter(game, "swarm_of_rats")
            if pulled:
                _spawn_engaged(game, pulled, inv)
                log(f"🐀 遭遇：好事魔宠——【{game.state.card_name(pulled)}】生成并与你交战")
            else:
                log("🐀 遭遇：好事魔宠——遭遇牌堆/弃牌堆中未找到鼠群")
            game.damage_engine.deal_damage(investigator_id, damage=1)
        return {"pending": False, "message": card_id}

    if card_id == "ghostly_presence":
        nahab = _find_in_play(game, "nahab")
        if nahab is None:
            pulled = _pull_card_from_encounter(game, "nahab")
            if pulled:
                _spawn_at_location(game, pulled, inv.location_id)
                log(f"👻 遭遇：鬼影骤现——【{game.state.card_name(pulled)}】生成在你所在地点")
            else:
                log("👻 遭遇：鬼影骤现——遭遇牌堆/弃牌堆中未找到那赫卜")
            return {"pending": False, "message": card_id}
        inst = game.state.get_card_instance(nahab)
        inst.exhausted = False
        # 简化：猎手直接移至抽牌调查员地点（官方逐地点移动）
        _move_enemy_to_location(game, nahab, inv.location_id)
        for other in game.state.get_investigators_at_location(inv.location_id):
            if not other.is_defeated:
                _enemy_attack(game, nahab, other.investigator_id)
        if inv.location_id == "site_of_the_sacrifice":
            inst.doom += 1
            controller._check_agenda_threshold()
            log("👻 那赫卜位于献祭场所，+1毁灭")
        log("👻 遭遇：鬼影骤现——那赫卜准备、移动并攻击其地点的所有调查员")
        return {"pending": False, "message": card_id}

    if card_id == "extradimensional_visions":
        difficulty = 2 + len(game.state.scenario.encounter_discard) // 10
        log(f"🌀 遭遇：异次元幻象（意志{difficulty}，失败弃1支援）")

        def on_fail(r):
            # 简化：自动弃第一个支援（官方自选）
            for iid in list(inv.play_area):
                cd = game.state.get_card_data(
                    game.state.get_card_instance(iid).card_id
                    if game.state.get_card_instance(iid) else "")
                if cd is not None and cd.type.value == "asset":
                    game.damage_engine._remove_card_from_play(iid)
                    log(f"  → 弃掉【{game.state.card_name(cd.id)}】")
                    return
        run_test(investigator_id, skill=Skill.WILLPOWER, difficulty=difficulty,
                 on_failure=on_fail)
        return {"pending": False, "message": card_id}

    if card_id == "pulled_by_the_stars":
        _place_in_threat(game, inv, card_id)
        svars.setdefault(card_id, {})[investigator_id] = {"moved": False}

        move_holder: list[Any] = []
        end_holder: list[Any] = []

        def _on_move(ctx):
            if _threat_gone(game, inv, card_id, investigator_id):
                game.event_bus.unregister(move_holder[0])
                return
            if ctx.investigator_id == investigator_id:
                rec = svars.get(card_id, {}).get(investigator_id)
                if rec is not None:
                    rec["moved"] = True

        def _on_turn_ends(ctx):
            if ctx.investigator_id != investigator_id:
                return
            if _threat_gone(game, inv, card_id, investigator_id):
                game.event_bus.unregister(end_holder[0])
                return
            rec = svars.get(card_id, {}).get(investigator_id)
            if rec is None:
                return
            if not rec.get("moved"):
                game.damage_engine.deal_damage(investigator_id, horror=2)
                log("✨ 群星牵引：本回合未移动，受2恐惧")
            rec["moved"] = False

        move_holder.append(game.event_bus.register(
            GameEvent.MOVE_ACTION_INITIATED, _on_move, priority=TimingPriority.AFTER))
        end_holder.append(game.event_bus.register(
            GameEvent.INVESTIGATOR_TURN_ENDS, _on_turn_ends,
            priority=TimingPriority.AFTER))
        log("✨ 遭遇：群星牵引——放入威胁区（回合结束未移动受2恐惧；"
            "可用 activate_discard_hex 花1行动检定意志3弃掉）")
        return {"pending": False, "message": card_id}

    if card_id == "disquieting_dreams":
        result = {"pending": False, "message": card_id}
        log("💤 遭遇：不安的梦（意志5，失败放入威胁区）")

        def on_fail(r):
            _place_in_threat(game, inv, card_id)
            svars.setdefault(card_id, {})[investigator_id] = True
            holder: list[Any] = []

            def _on_turn_ends(ctx):
                if ctx.investigator_id != investigator_id:
                    return
                if _threat_gone(game, inv, card_id, investigator_id):
                    game.event_bus.unregister(holder[0])
                    return
                deck = game.state.scenario.encounter_deck
                if deck:
                    cid = deck.pop(0)
                    game.state.scenario.encounter_discard.append(cid)
                    log(f"💤 不安的梦：回合结束，弃掉遭遇堆顶【{game.state.card_name(cid)}】")

            holder.append(game.event_bus.register(
                GameEvent.INVESTIGATOR_TURN_ENDS, _on_turn_ends,
                priority=TimingPriority.AFTER))
        run_test(investigator_id, skill=Skill.WILLPOWER, difficulty=5,
                 on_failure=on_fail)
        return result

    # ---- The Wages of Sin ----
    if card_id == "punishment":
        _place_in_threat(game, inv, card_id)
        svars.setdefault(card_id, {})[investigator_id] = True
        holder: list[Any] = []

        def _on_enemy_defeated(_ctx):
            if _threat_gone(game, inv, card_id, investigator_id):
                game.event_bus.unregister(holder[0])
                return
            game.damage_engine.deal_damage(investigator_id, damage=1)
            log("🔨 惩罚：有敌人被击败，受1伤害")

        holder.append(game.event_bus.register(
            GameEvent.ENEMY_DEFEATED, _on_enemy_defeated,
            priority=TimingPriority.AFTER))
        log("🔨 遭遇：惩罚——放入威胁区（敌人被击败后受1伤害；"
            "可用 activate_discard_hex 花1行动检定意志3弃掉）")
        return {"pending": False, "message": card_id}

    if card_id == "burdens_of_the_past":
        copies = [iid for iid in inv.threat_area
                  if (game.state.get_card_instance(iid) is not None
                      and game.state.get_card_instance(iid).card_id.startswith(
                          "unfinished_business"))]
        if not copies:
            log("⌛ 遭遇：往昔重担——威胁区无未了之事，涌动")
            return _surge()
        # 简化：未了之事的强制能力不在卡牌数据中（引擎缺口），记录触发次数，
        # 实际结算由剧本层负责
        svars["unfinished_business_triggered"] = \
            int(svars.get("unfinished_business_triggered", 0)) + len(copies)
        log(f"⌛ 遭遇：往昔重担——触发{len(copies)}张未了之事的强制能力（由剧本层结算）")
        return {"pending": False, "message": card_id}

    if card_id == "ominous_portents":
        spectral = svars.get("spectral_encounter_deck") or []
        if choice is None and spectral:
            svars["pending_choice"] = {
                "card_id": card_id,
                "investigator_id": investigator_id,
                "prompt": "凶兆：选择 抽幽灵遭遇牌堆顶 或 检定意志3（失败受2恐惧）",
                "options": [
                    {"id": "draw_spectral", "label": "抽取幽灵遭遇牌堆顶上的1张卡牌"},
                    {"id": "test", "label": "检定意志3，失败受2恐惧"},
                ],
            }
            return {"pending": True, "message": "pending_choice"}
        if choice == "draw_spectral" and spectral:
            cid = spectral.pop(0)
            log(f"🔮 遭遇：凶兆——抽取幽灵遭遇牌堆顶【{game.state.card_name(cid)}】"
                "（祸害/不可取消未强制）")
            controller.resolve_encounter_card(cid, investigator_id=investigator_id)
            return {"pending": False, "message": card_id}
        log("🔮 遭遇：凶兆（意志3，失败受2恐惧）")
        run_test(investigator_id, skill=Skill.WILLPOWER, difficulty=3,
                 on_failure=lambda r: game.damage_engine.deal_damage(
                     investigator_id, horror=2))
        return {"pending": False, "message": card_id}

    if card_id == "grave_light":
        if svars.get("drawing_from_spectral"):
            game.damage_engine.deal_damage(investigator_id, damage=2)
            game.state.scenario.encounter_discard.append(card_id)
            log("🕯️ 遭遇：长明灯——从幽灵遭遇牌堆抽出，受2伤害")
            return {"pending": False, "message": card_id}
        spectral = svars.setdefault("spectral_encounter_deck", [])
        spectral.append(card_id)
        random.shuffle(spectral)
        log("🕯️ 遭遇：长明灯——洗入幽灵遭遇牌堆，涌动")
        return _surge()

    if card_id == "bane_of_the_living":
        ubs = [iid for o in game.state.investigators.values() for iid in o.threat_area
               if (game.state.get_card_instance(iid) is not None
                   and game.state.get_card_instance(iid).card_id.startswith(
                       "unfinished_business"))]
        spectral = svars.get("spectral_encounter_deck") or []
        can_geist = any(_is_enemy_with_tag(game, c, "geist") for c in spectral)
        if choice is None and ubs and can_geist:
            svars["pending_choice"] = {
                "card_id": card_id,
                "investigator_id": investigator_id,
                "prompt": "祸害生者：选择 翻面未了之事 或 翻幽灵牌堆直到灵怪并生成",
                "options": [
                    {"id": "flip", "label": "将1张未了之事翻面至异端者面并放置一半伤害"},
                    {"id": "geist", "label": "翻幽灵遭遇牌堆直到灵怪敌人，生成并与你交战"},
                ],
            }
            return {"pending": True, "message": "pending_choice"}
        if choice == "flip" and ubs or (choice is None and ubs and not can_geist):
            # 简化：翻面/放置伤害记录进 vars（未了之事数据缺失，引擎缺口）
            svars["unfinished_business_flipped"] = \
                int(svars.get("unfinished_business_flipped", 0)) + 1
            log("🧟 遭遇：祸害生者——1张未了之事翻面至异端者面（由剧本层结算）")
            return {"pending": False, "message": card_id}
        found = None
        while spectral:
            cid = spectral.pop(0)
            if _is_enemy_with_tag(game, cid, "geist"):
                found = cid
                break
            svars.setdefault("spectral_encounter_discard", []).append(cid)
        if found:
            _spawn_engaged(game, found, inv)
            log(f"🧟 遭遇：祸害生者——【{game.state.card_name(found)}】生成并与你交战")
        else:
            log("🧟 遭遇：祸害生者——幽灵遭遇牌堆中无灵怪敌人")
        return {"pending": False, "message": card_id}

    # ---- Union and Disillusion ----
    if card_id == "call_to_order":
        s = game.state.scenario
        cultists = [c for c in reversed(s.encounter_discard)
                    if _is_enemy_with_tag(game, c, "cultist")][:2]
        # “无人地点”：无调查员且无敌人；取剩余线索最多者
        best_loc = None
        best = -1
        for loc in game.state.locations.values():
            if loc.enemies:
                continue
            if any(o.location_id == loc.location_id and not o.is_defeated
                   for o in game.state.investigators.values()):
                continue
            if loc.clues > best:
                best, best_loc = loc.clues, loc
        spawned = 0
        if best_loc is not None:
            for cid in cultists:
                s.encounter_discard.remove(cid)
                _spawn_at_location(game, cid, best_loc.location_id)
                spawned += 1
        if spawned == 0:
            log("📣 遭遇：发号施令——无异教徒敌人生成，涌动")
            return _surge()
        log(f"📣 遭遇：发号施令——{spawned}个异教徒敌人生成在【{best_loc.location_id}】")
        return {"pending": False, "message": card_id}

    if card_id == "expulsion":
        target = _nearest_enemy_with_tag(game, inv, "cultist")
        if target is None:
            log("⚔️ 遭遇：除籍——场上无异教徒敌人，涌动")
            return _surge()
        inst = game.state.get_card_instance(target)
        inst.exhausted = False
        # 简化：直接移至调查员地点交战（官方逐地点移动，结果相同）
        _engage_investigator(game, target, inv)
        _enemy_attack(game, target, investigator_id)
        moved_keys = [k for k in _keys_of(game, investigator_id) if k in _KEY_NAMES]
        if moved_keys:
            held = svars.get("keys", {}).get(investigator_id, [])
            svars["keys"][investigator_id] = \
                [k for k in held if k not in _KEY_NAMES]
            svars.setdefault("enemy_keys", {}).setdefault(target, []).extend(moved_keys)
        log(f"⚔️ 遭遇：除籍——【{game.state.card_name(inst.card_id)}】准备、交战并立即攻击"
            + (f"，你的{len(moved_keys)}把钥匙放到它身上" if moved_keys else ""))
        return {"pending": False, "message": card_id}

    if card_id == "beneath_the_lodge":
        has_key = any(k in _KEY_NAMES for k in _keys_of(game, investigator_id))
        difficulty = 3 + (1 if has_key else 0)
        log(f"⛪ 遭遇：秘社地底（智力{difficulty}，失败按差额失去线索或受恐惧）")

        def on_fail(r):
            m = _margin_fail(r)
            for _ in range(m):
                # 简化：自动优先失去线索，无线索则受恐惧（官方逐点二选一）
                if inv.clues > 0:
                    inv.clues -= 1
                else:
                    game.damage_engine.deal_damage(investigator_id, horror=1)
        run_test(investigator_id, skill=Skill.INTELLECT, difficulty=difficulty,
                 on_failure=on_fail)
        return {"pending": False, "message": card_id}

    if card_id == "mark_of_the_order":
        for other_id, keys in (svars.get("keys") or {}).items():
            other = game.state.get_investigator(other_id)
            if other is None or other.is_defeated:
                continue
            for k in list(keys):
                if k == "skull":
                    game.damage_engine.deal_damage(other_id, damage=1)
                elif k == "cultist":
                    game.damage_engine.deal_damage(other_id, horror=1)
                elif k == "tablet":
                    for cid in random.sample(other.hand, min(2, len(other.hand))):
                        other.hand.remove(cid)
                        other.discard.append(cid)
                elif k == "elder_thing":
                    other.resources = max(0, other.resources - 3)
        log("🔑 遭遇：修道会符号——按持有者钥匙结算惩罚，涌动")
        return _surge()

    # ---- In the Clutches of Chaos ----
    if card_id == "death_approaches":
        # 简化：自动放入抽牌调查员的威胁区（官方任选调查员）；
        # “将要受恐惧时额外+2”未强制（HORROR_ASSIGNED 只支持减免，引擎缺口）
        _place_in_threat(game, inv, card_id)
        svars.setdefault(card_id, {})[investigator_id] = True
        log("💀 遭遇：死期临近——放入威胁区（将要受恐惧时额外+2[未强制]），涌动")
        return _surge()

    if card_id == "marked_for_death":
        difficulty = 2 + inv.horror
        log(f"🎯 遭遇：死亡记号（敏捷{difficulty}，失败受2伤害）")
        run_test(investigator_id, skill=Skill.AGILITY, difficulty=difficulty,
                 on_failure=lambda r: game.damage_engine.deal_damage(
                     investigator_id, damage=2))
        return {"pending": False, "message": card_id}

    if card_id == "watchers_gaze":
        log("👁️ 遭遇：看守人的注视——每位调查员检定意志5，失败结算闹鬼")

        def _make_fail(target_id):
            def on_fail(_r):
                target = game.state.get_investigator(target_id)
                if target is None:
                    return
                # 简化：自动结算自己地点的闹鬼（官方也可选幽灵看守人地点）
                _resolve_haunted(controller, target.location_id, target_id)
            return on_fail
        for other_id in list(game.state.player_order):
            other = game.state.get_investigator(other_id)
            if other is None or other.is_defeated:
                continue
            run_test(other_id, skill=Skill.WILLPOWER, difficulty=5,
                     on_failure=_make_fail(other_id))
        return {"pending": False, "message": card_id}

    if card_id == "chaos_manifest":
        log("🌌 遭遇：混沌幽现（意志3，失败按差额在随机地点放裂口）")

        def on_fail(r):
            x = _margin_fail(r)
            loc_ids = list(game.state.locations)
            for loc_id in random.sample(loc_ids, min(x, len(loc_ids))):
                _add_breaches(game, loc_id, 1)
                log(f"  → 【{loc_id}】+1裂口")
        run_test(investigator_id, skill=Skill.WILLPOWER, difficulty=3,
                 on_failure=on_fail)
        return {"pending": False, "message": card_id}

    if card_id == "primordial_gateway":
        loc_ids = list(game.state.locations)
        if not loc_ids:
            log("🚪 遭遇：元初通道——无地点可叠加")
            return {"pending": False, "message": card_id}
        loc_id = random.choice(loc_ids)
        controller.attach_card_to_location(card_id, loc_id)
        missing = 3 - _breach_count(game, loc_id)
        if missing > 0:
            _add_breaches(game, loc_id, missing)
        # 简化：叠加地点文本框视为空白未强制（无地点文本系统，引擎缺口）
        log(f"🚪 遭遇：元初通道——叠加到【{loc_id}】并补足3裂口"
            "（地点文本空白[未强制]；可用 activate_close_gateway 检定关闭）")
        return {"pending": False, "message": card_id}

    if card_id == "terror_unleashed":
        loc_id = inv.location_id
        if _breach_count(game, loc_id) == 0:
            _add_breaches(game, loc_id, 1)
        loc = game.state.get_location(loc_id)
        x = (loc.doom if loc else 0) + _breach_count(game, loc_id)
        # 简化：X点伤害/恐惧自动全取恐惧（官方自行分配）
        game.damage_engine.deal_damage(investigator_id, horror=x)
        log(f"👹 遭遇：猛鬼出笼——所在地点毁灭+裂口共{x}，受{x}恐惧")
        return {"pending": False, "message": card_id}

    if card_id == "secrets_of_the_beyond":
        best = None
        best_doom = 0
        for iid in _enemies_with_tag(game, "cultist"):
            inst = game.state.get_card_instance(iid)
            if inst is not None and inst.doom > best_doom:
                best, best_doom = iid, inst.doom
        if best is None:
            log("📖 遭遇：异界之秘——无异教徒敌人带有毁灭，涌动")
            return _surge()
        loc_id = _enemy_location(game, best)
        if loc_id:
            _add_breaches(game, loc_id, best_doom)
        log(f"📖 遭遇：异界之秘——【{_enemy_location(game, best)}】+{best_doom}裂口")
        return {"pending": False, "message": card_id}

    if card_id == "toil_and_trouble":
        s = game.state.scenario
        power = None
        for cid in reversed(s.encounter_discard):
            cd = game.state.get_card_data(cid)
            if cd is not None and cd.type.value == "treachery" \
                    and "power" in _card_tags(game, cid):
                power = cid
                break
        if choice is None and power is not None:
            svars["pending_choice"] = {
                "card_id": card_id,
                "investigator_id": investigator_id,
                "prompt": "不惮辛劳不惮烦：选择 结算弃牌堆顶力量诡计的显现 或 结算入侵",
                "options": [
                    {"id": "resolve_power", "label": f"结算【{game.state.card_name(power)}】的显现能力"},
                    {"id": "incursion", "label": "在你所在地点结算一次入侵"},
                ],
            }
            return {"pending": True, "message": "pending_choice"}
        if choice == "resolve_power" and power is not None:
            # 简化：卡牌留在弃牌堆；其涌动（若有）不生效——并非抽取
            log(f"🧹 遭遇：不惮辛劳不惮烦——结算【{game.state.card_name(power)}】的显现能力")
            controller.resolve_encounter_card(power, investigator_id=investigator_id)
        else:
            # 简化：入侵机制未实现（引擎缺口），记录次数由剧本层结算
            inc = svars.setdefault("incursions", {})
            inc[inv.location_id] = int(inc.get(inv.location_id, 0)) + 1
            log(f"🧹 遭遇：不惮辛劳不惮烦——在【{inv.location_id}】结算一次入侵（由剧本层结算）")
        return {"pending": False, "message": card_id}

    # ---- Before the Black Throne ----
    if card_id == "ultimate_chaos":
        result = {"pending": False, "message": card_id}
        az = _find_in_play(game, "azathoth")
        log("🌑 遭遇：究极混沌（意志4，失败叠加到阿撒托斯；2+受1伤1恐；3+涌动）")

        def on_fail(r):
            m = _margin_fail(r)
            if m >= 2:
                game.damage_engine.deal_damage(investigator_id, damage=1, horror=1)
            if m >= 3:
                result["surge"] = True
                result["message"] = "surge"
            if az is None:
                return
            attached = svars.setdefault("ultimate_chaos_attached", [])
            iid = game.state.next_instance_id()
            game.state.cards_in_play[iid] = CardInstance(
                instance_id=iid, card_id=card_id,
                owner_id="scenario", controller_id="scenario", attached_to=az)
            attached.append(iid)
            if len(attached) >= 3:
                for x in attached:
                    game.state.cards_in_play.pop(x, None)
                    game.state.scenario.encounter_discard.append(card_id)
                attached.clear()
                # 简化：自动选择在阿撒托斯上+1毁灭（官方二选一：或攻击每位调查员）
                inst = game.state.get_card_instance(az)
                inst.doom += 1
                controller._check_agenda_threshold()
                log("  → 集齐3张究极混沌：弃掉并在阿撒托斯上+1毁灭")
        run_test(investigator_id, skill=Skill.WILLPOWER, difficulty=4,
                 on_failure=on_fail)
        return result

    if card_id == "whispered_bargain":
        az = _find_in_play(game, "azathoth")
        if az is None:
            log("🤝 遭遇：耳语契约——阿撒托斯不在场，无效果")
            return {"pending": False, "message": card_id}
        if choice is None:
            svars["pending_choice"] = {
                "card_id": card_id,
                "investigator_id": investigator_id,
                "prompt": "耳语契约：选择 阿撒托斯+1毁灭 或 阿撒托斯攻击你",
                "options": [
                    {"id": "place_doom", "label": "在阿撒托斯上放置1毁灭"},
                    {"id": "attack", "label": "阿撒托斯攻击你"},
                ],
            }
            return {"pending": True, "message": "pending_choice"}
        if choice == "attack":
            _enemy_attack(game, az, investigator_id)
            log("🤝 遭遇：耳语契约——阿撒托斯攻击你")
        else:
            inst = game.state.get_card_instance(az)
            inst.doom += 1
            controller._check_agenda_threshold()
            log("🤝 遭遇：耳语契约——阿撒托斯+1毁灭")
        return {"pending": False, "message": card_id}

    if card_id == "the_end_is_nigh":
        s = game.state.scenario
        x = s.current_agenda_index + 1 if s.current_agenda is not None else 4
        difficulty = 1 + x
        log(f"📯 遭遇：终结将至（意志{difficulty}，失败将异教徒的毁灭移到阿撒托斯）")

        def on_fail(r):
            az = _find_in_play(game, "azathoth")
            if az is None:
                log("  → 阿撒托斯不在场，毁灭流失")
                return
            az_inst = game.state.get_card_instance(az)
            cultists = _enemies_with_tag(game, "cultist")
            if cultists:
                total = 0
                for iid in cultists:
                    inst = game.state.get_card_instance(iid)
                    total += inst.doom
                    inst.doom = 0
                az_inst.doom += total
                log(f"  → {total}点毁灭从异教徒移到阿撒托斯")
            else:
                az_inst.doom += 1
                log("  → 无异教徒敌人，阿撒托斯+1毁灭")
            controller._check_agenda_threshold()
        run_test(investigator_id, skill=Skill.WILLPOWER, difficulty=difficulty,
                 on_failure=on_fail)
        return {"pending": False, "message": card_id}

    if card_id == "a_world_in_darkness":
        az = _find_in_play(game, "azathoth")
        doom = game.state.get_card_instance(az).doom if az else 0
        if doom <= 0:
            log("🌍 遭遇：黑暗世界——阿撒托斯上无毁灭，涌动")
            return _surge()
        for _ in range(doom):
            # 简化：逐点自动选择——有资源先失资源，否则弃手牌，否则受恐惧
            # （官方四选一：失1资源/弃1手牌/受1恐惧/受1伤害）
            if inv.resources > 0:
                inv.resources -= 1
            elif inv.hand:
                cid = inv.hand.pop(0)
                inv.discard.append(cid)
            else:
                game.damage_engine.deal_damage(investigator_id, horror=1)
        log(f"🌍 遭遇：黑暗世界——按阿撒托斯上{doom}点毁灭结算惩罚")
        return {"pending": False, "message": card_id}

    return None


# ---------------------------------------------------------------------------
# 公开激活方法 / 引擎缺口注入点（供 session 层/测试调用）
# ---------------------------------------------------------------------------

def activate_discard_hex(controller, investigator_id: str, card_id: str) -> bool:
    """[行动]：检定意志3，成功弃掉威胁区中的 Hex 诡计（wracked/bedeviled/
    pulled_by_the_stars/punishment）。所在地点有消耗状态的女巫敌人时自动成功。"""
    game = controller.game
    inv = game.state.get_investigator(investigator_id)
    if inv is None or inv.actions_remaining < 1:
        return False
    if card_id not in _HEX_CARDS or _threat_copy(game, inv, card_id) is None:
        return False
    inv.actions_remaining -= 1
    if _exhausted_witch_at(game, inv.location_id):
        _discard_threat_copy(game, inv, card_id)
        controller.log(f"🕸️ 消耗的女巫在场：自动成功，弃掉【{game.state.card_name(card_id)}】")
        return True

    def _ok(_r):
        _discard_threat_copy(game, inv, card_id)
        controller.log(f"🕸️ 检定成功：弃掉【{game.state.card_name(card_id)}】")

    # _run_skill_test 不暴露成功回调，直接调用检定引擎
    game.skill_test_engine.run_test(
        investigator_id=investigator_id, skill_type=Skill.WILLPOWER,
        difficulty=3, committed_card_ids=[],
        on_success=_ok, on_failure=lambda r: None)
    return True


def activate_close_gateway(controller, investigator_id: str,
                           skill: str = "intellect") -> bool:
    """[行动]：检定智力或意志(4)关闭元初通道，成功弃掉 primordial_gateway。

    简化：要求调查员在被叠加地点。
    """
    game = controller.game
    inv = game.state.get_investigator(investigator_id)
    if inv is None or inv.actions_remaining < 1:
        return False
    iid = controller.location_attachment_instance(inv.location_id,
                                                  "primordial_gateway")
    if iid is None:
        return False
    skill_type = Skill.WILLPOWER if skill == "willpower" else Skill.INTELLECT
    inv.actions_remaining -= 1

    def _ok(_r):
        controller.detach_card_from_location(iid)
        controller.log("🚪 检定成功：关闭并弃掉【元初通道】")

    game.skill_test_engine.run_test(
        investigator_id=investigator_id, skill_type=skill_type,
        difficulty=4, committed_card_ids=[],
        on_success=_ok, on_failure=lambda r: None)
    return True


def notify_encounter_deck_empty(controller) -> None:
    """“遭遇牌堆耗尽”强制触发点（引擎缺口：无此事件；由剧本/会话层调用）。

    - evil_past：受2恐惧并检定意志3，成功弃掉。
    - disquieting_dreams：弃掉，翻开牌堆顶10张，抽取其中弱点、弃掉其余。
      （简化：抽取弱点不触发其显现。）
    """
    game = controller.game
    for inv_id in list(game.state.player_order):
        inv = game.state.get_investigator(inv_id)
        if inv is None or inv.is_defeated:
            continue
        if _threat_copy(game, inv, "evil_past") is not None:
            game.damage_engine.deal_damage(inv_id, horror=2)
            controller.log("🌑 邪恶往昔：遭遇牌堆耗尽——受2恐惧并检定意志3")

            def _ok(_r, inv=inv):
                if _discard_threat_copy(game, inv, "evil_past"):
                    controller.log("🌑 邪恶往昔：检定成功，弃掉")

            game.skill_test_engine.run_test(
                investigator_id=inv_id, skill_type=Skill.WILLPOWER,
                difficulty=3, committed_card_ids=[],
                on_success=_ok, on_failure=lambda r: None)
        if _threat_copy(game, inv, "disquieting_dreams") is not None:
            _discard_threat_copy(game, inv, "disquieting_dreams")
            revealed = [inv.deck.pop(0) for _ in range(min(10, len(inv.deck)))]
            drawn = []
            for cid in revealed:
                if is_weakness_card(game.state.get_card_data(cid)):
                    inv.hand.append(cid)
                    drawn.append(cid)
                else:
                    inv.discard.append(cid)
            controller.log(
                f"💤 不安的梦：遭遇牌堆耗尽——翻开牌堆顶{len(revealed)}张，"
                f"抽取弱点【{_log_names(game, drawn)}】，弃掉其余")
