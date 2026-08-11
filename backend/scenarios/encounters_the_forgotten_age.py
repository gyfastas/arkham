"""The Forgotten Age encounter treachery resolution.

Called from ScenarioController.resolve_encounter_card as a fallback branch
(wiring done elsewhere). `resolve_treachery` returns a result dict or None
(to continue to the next matcher). Choice cards set
`scenario.vars["pending_choice"]` (with an "investigator_id" field for
multiplayer routing) and are re-entered with `choice=<option_id>`.
Cards with Surge return {"surge": True}.

Simplifications (also documented per card below):

- TFA campaign state that has no engine home lives in `scenario.vars`:
  "depth" (current depth level, default 0), "vengeance" (explicit override;
  otherwise parsed from `Vengeance N` text of cards in the victory display),
  "in_pursuit" (list of enemy card ids pursuing the group — The Depths of
  Yoth mechanic; the engine has no pursuit zone), "exploration_deck"
  (list of card ids), "supplies" (investigator_id -> supply id list, e.g.
  "pickaxe" / "torches"), "interviewed_subjects" (count),
  "nexus_location_id" (Nexus of N'kai location).
- Poisoned status is tracked by the Poisoned weakness card in the
  investigator's threat area; set-aside copies are created on demand.
- Ongoing restrictions (cannot move/explore/investigate/draw, blanked Item
  assets, +1 action to investigate, enemy stat buffs, agenda doom
  threshold -1) are recorded in `scenario.vars` and NOT enforced by the
  engine (no hook points); each in-play card's [action] ability is exposed
  as a public `activate_*` function for the session layer / tests.
- Revelation-time "choose one" effects use pending_choice; choices *inside*
  a failed skill test resolve deterministically (documented per card).
- TFA encounter data stores traits in English, so trait checks scan both
  `keywords` and `traits` (same as the Carcosa branch).
"""

from __future__ import annotations

import random
import re
from typing import Any

from backend.models.enums import CardType, GameEvent, Skill, TimingPriority
from backend.models.state import CardData, CardInstance

# ---------------------------------------------------------------------------
# 通用辅助
# ---------------------------------------------------------------------------


def _margin_fail(result) -> int:
    return max(0, (getattr(result, "difficulty", 0) or 0) - (getattr(result, "modified_skill", 0) or 0))


def _log_names(game, cids: list[str]) -> str:
    return "、".join(game.state.card_name(c) for c in cids)


def _tags_of_cd(cd) -> list[str]:
    if cd is None:
        return []
    return list(getattr(cd, "keywords", None) or []) + list(getattr(cd, "traits", None) or [])


def _tags_of(game, instance_id: str) -> list[str]:
    inst = game.state.get_card_instance(instance_id)
    if inst is None:
        return []
    return _tags_of_cd(game.state.get_card_data(inst.card_id))


def _enemies_with_tag(game, tag: str) -> list[str]:
    out = []
    for iid, inst in game.state.cards_in_play.items():
        cd = game.state.get_card_data(inst.card_id)
        if cd is None or cd.type.value != "enemy":
            continue
        if tag in _tags_of_cd(cd):
            out.append(iid)
    return out


def _nearest_enemy_with_tag(game, inv, tag: str) -> str | None:
    """最近的带 tag 敌人（交战 > 同地点 > 任意）。"""
    for iid in inv.threat_area:
        if tag in _tags_of(game, iid):
            return iid
    loc = game.state.get_location(inv.location_id)
    if loc is not None:
        for iid in loc.enemies:
            if tag in _tags_of(game, iid):
                return iid
    for iid in _enemies_with_tag(game, tag):
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


def _remove_from_threat(game, inv, instance_id: str, *, to_encounter_discard: bool = True) -> None:
    inst = game.state.cards_in_play.pop(instance_id, None)
    if inst is None:
        return
    if instance_id in inv.threat_area:
        inv.threat_area.remove(instance_id)
    if to_encounter_discard:
        game.state.scenario.encounter_discard.append(inst.card_id)


def _register_one_shot(game, event: GameEvent, handler) -> None:
    """Register an event handler that unregisters itself after firing once."""
    holder: list[Any] = []

    def _wrap(ctx):
        entry = holder[0]
        game.event_bus.unregister(entry)
        handler(ctx)

    holder.append(game.event_bus.register(event, _wrap, priority=TimingPriority.AFTER))


def _run_test_full(controller, investigator_id: str, *, skill, difficulty: int,
                   on_success=None, on_failure=None) -> None:
    """_run_skill_test 的双回调版本（成功/失败都需要结算时使用）。"""
    _ok = on_success or (lambda r: None)
    _fail = on_failure or (lambda r: None)
    if controller.skill_test_request_handler is not None:
        controller.skill_test_request_handler(
            investigator_id=investigator_id, skill=skill, difficulty=difficulty,
            on_success=_ok, on_failure=_fail)
        return
    controller.game.skill_test_engine.run_test(
        investigator_id=investigator_id, skill_type=skill, difficulty=difficulty,
        committed_card_ids=[], on_success=_ok, on_failure=_fail)


def _each_investigator(game):
    for inv_id in list(game.state.player_order):
        other = game.state.get_investigator(inv_id)
        if other is not None and not other.is_defeated:
            yield other


# ---------------------------------------------------------------------------
# TFA 状态辅助（scenario.vars）
# ---------------------------------------------------------------------------


def _is_poisoned(game, inv) -> bool:
    return _threat_copy(game, inv, "poisoned") is not None


def _put_poisoned(game, inv) -> bool:
    """将搁置的 Poisoned 弱点放入威胁区（限1）。返回是否实际放入。"""
    if _is_poisoned(game, inv):
        return False
    _place_in_threat(game, inv, "poisoned")
    return True


def _vengeance_points(game) -> int:
    """复仇点数：vars["vengeance"] 优先；否则从胜利牌区卡面 `Vengeance N` 解析。

    简化：`Vengeance X`（变量）无法求值，按 0 计。
    """
    svars = game.state.scenario.vars
    if svars.get("vengeance") is not None:
        return int(svars["vengeance"] or 0)
    total = 0
    for cid in game.state.scenario.victory_display:
        cd = game.state.get_card_data(cid)
        text = getattr(cd, "text", "") or ""
        for m in re.findall(r"[Vv]engeance (\d+)", text):
            total += int(m)
    return total


def _depth(game) -> int:
    """当前深度等级（The Depths of Yoth；默认 0，由剧本层写入 vars["depth"]）。"""
    return int(game.state.scenario.vars.get("depth", 0) or 0)


def _supplies(game, investigator_id: str) -> list[str]:
    return list(game.state.scenario.vars.get("supplies", {}).get(investigator_id, []) or [])


def _exploration_deck(game) -> list[str]:
    return game.state.scenario.vars.setdefault("exploration_deck", [])


def _shuffle_into_exploration_deck(game, card_id: str) -> None:
    deck = _exploration_deck(game)
    deck.append(card_id)
    random.shuffle(deck)


def _location_traits(game, location_id: str) -> list[str]:
    loc = game.state.get_location(location_id)
    cd = getattr(loc, "card_data", None) if loc is not None else None
    return _tags_of_cd(cd)


def _locations_with_trait(game, trait: str) -> list[str]:
    return [lid for lid in game.state.locations
            if trait in _location_traits(game, lid)]


def _nexus_location_id(game) -> str | None:
    svars = game.state.scenario.vars
    if svars.get("nexus_location_id") in game.state.locations:
        return svars["nexus_location_id"]
    for lid, loc in game.state.locations.items():
        if getattr(loc.card_data, "id", None) == "nexus_of_nkai":
            return lid
    return None


def _ally_assets(game, inv) -> list[str]:
    out = []
    for iid in inv.play_area:
        inst = game.state.get_card_instance(iid)
        cd = game.state.get_card_data(inst.card_id) if inst else None
        if cd is None or cd.type.value != "asset":
            continue
        tags = _tags_of_cd(cd)
        if "ally" in tags or "盟友" in tags:
            out.append(iid)
    return out


def _enemy_attack(game, instance_id: str, investigator_id: str) -> None:
    inst = game.state.get_card_instance(instance_id)
    cd = game.state.get_card_data(inst.card_id) if inst else None
    if cd is None:
        return
    game.damage_engine.deal_damage(
        investigator_id, damage=cd.enemy_damage or 0,
        horror=cd.enemy_horror or 0, source=instance_id)


def _round_end_countdown(game, flag: str) -> None:
    """"放在密谋旁"类卡牌：每轮结束弃掉1张（每轮最多一次）。

    只在首张入场时注册处理器（多张在场也只每轮弃1张）。
    """
    if game.state.scenario.vars.get(flag, 0) != 1:
        return

    holder: list[Any] = []

    def _on_round_end(_ctx):
        left = game.state.scenario.vars.get(flag, 0)
        if left <= 1:
            game.state.scenario.vars.pop(flag, None)
            game.event_bus.unregister(holder[0])
        else:
            game.state.scenario.vars[flag] = left - 1

    holder.append(game.event_bus.register(GameEvent.ROUND_ENDS, _on_round_end,
                                          priority=TimingPriority.AFTER))


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------


def resolve_treachery(controller, card_id: str, *, investigator_id: str,
                      choice: str | None = None) -> dict | None:
    """结算本循环遭遇卡。未处理返回 None；需要选择时写 pending_choice。"""
    game = controller.game
    inv = game.state.get_investigator(investigator_id)
    if inv is None:
        return None
    log = controller.log
    run_test = controller._run_skill_test
    svars = game.state.scenario.vars

    # ---- Rainforest ----
    if card_id == "overgrowth":
        if controller.location_attachment_instance(inv.location_id, "overgrowth"):
            # 每地点限1：无法叠加，直接弃掉（官方无涌动）
            log("🌿 遭遇：瘋狂生長——所在地点已有，弃掉")
            return {"pending": False, "message": "overgrowth"}
        controller.attach_card_to_location("overgrowth", inv.location_id)
        svars.setdefault("overgrowth", {})[inv.location_id] = True
        log("🌿 遭遇：瘋狂生長——叠加到所在地点（不能探索[未强制]；"
            "可用 activate_overgrowth 检定战斗/智力4弃掉）")
        return {"pending": False, "message": "overgrowth"}

    if card_id == "voice_of_the_jungle":
        iid = _place_in_threat(game, inv, "voice_of_the_jungle")
        svars.setdefault("voice_of_the_jungle", {})[investigator_id] = iid

        holder: list[Any] = []

        def _on_turn_end(ctx):
            if ctx.investigator_id != investigator_id:
                return
            if _threat_copy(game, inv, "voice_of_the_jungle") is None:
                game.event_bus.unregister(holder[0])
                return
            # 简化：探索成功记录由剧本层写入 vars["explored_this_turn"]（引擎无探索动作）
            explored = svars.setdefault("explored_this_turn", [])
            if investigator_id in explored:
                explored.remove(investigator_id)
                log("🌴 叢林之聲：本回合探索成功，无事发生")
            else:
                game.damage_engine.deal_damage(investigator_id, horror=1)
                log("🌴 叢林之聲：本回合未探索成功，受1恐惧")

        holder.append(game.event_bus.register(GameEvent.INVESTIGATOR_TURN_ENDS,
                                              _on_turn_end, priority=TimingPriority.AFTER))
        log("🌴 遭遇：叢林之聲——放入威胁区（回合结束未探索受1恐惧；"
            "可用 activate_voice_of_the_jungle 意志3弃掉）")
        return {"pending": False, "message": "voice_of_the_jungle"}

    # ---- Serpents ----
    if card_id == "snake_bite":
        log("🐍 遭遇：毒蛇噬咬（敏捷3，失败：盟友受5伤 或 1直接伤害+中毒）")

        def on_fail(_r):
            # 简化：自动优先选择对盟友造成5伤（官方二选一）
            allies = _ally_assets(game, inv)
            if allies:
                iid = allies[0]
                inst = game.state.get_card_instance(iid)
                inst.damage += 5
                log(f"  → 【{game.state.card_name(inst.card_id)}】受到5点伤害")
                game.damage_engine._check_asset_defeat(iid)
                return
            game.damage_engine.deal_damage(investigator_id, damage=1, direct=True)
            if _put_poisoned(game, inv):
                log("  → 受1直接伤害，中毒弱点放入威胁区")
            else:
                log("  → 受1直接伤害（已中毒）")
        run_test(investigator_id, skill=Skill.AGILITY, difficulty=3, on_failure=on_fail)
        return {"pending": False, "message": "snake_bite"}

    # ---- Expedition ----
    if card_id == "lost_in_the_wilds":
        log("🧭 遭遇：迷失荒野（意志3，失败按差额受恐惧并加入威胁区）")

        def on_fail(r):
            m = _margin_fail(r)
            if m:
                game.damage_engine.deal_damage(investigator_id, horror=m)
            if _threat_copy(game, inv, "lost_in_the_wilds") is None:
                _place_in_threat(game, inv, "lost_in_the_wilds")
            # 简化：不能移动/探索记入 vars，未强制（引擎无移动拦截钩子）
            svars.setdefault("lost_in_the_wilds", {})[investigator_id] = True

            holder: list[Any] = []

            def _on_turn_end(ctx):
                if ctx.investigator_id != investigator_id:
                    return
                game.event_bus.unregister(holder[0])
                iid = _threat_copy(game, inv, "lost_in_the_wilds")
                if iid is not None:
                    _remove_from_threat(game, inv, iid)
                svars.get("lost_in_the_wilds", {}).pop(investigator_id, None)
                log("🧭 迷失荒野：回合结束，弃掉")

            holder.append(game.event_bus.register(GameEvent.INVESTIGATOR_TURN_ENDS,
                                                  _on_turn_end, priority=TimingPriority.AFTER))
        run_test(investigator_id, skill=Skill.WILLPOWER, difficulty=3, on_failure=on_fail)
        return {"pending": False, "message": "lost_in_the_wilds"}

    if card_id == "low_on_supplies":
        if choice is None:
            svars["pending_choice"] = {
                "card_id": card_id,
                "investigator_id": investigator_id,
                "prompt": "補給短缺：你必须决定——每位调查员 失去2资源 / 受1伤害 / 弃1支援",
                "options": [
                    {"id": "lose_resources", "label": "每位调查员失去2资源"},
                    {"id": "take_damage", "label": "每位调查员受1伤害"},
                    {"id": "discard_asset", "label": "每位调查员选择并弃掉1张支援"},
                ],
            }
            return {"pending": True, "message": "pending_choice"}
        if choice == "lose_resources":
            for other in _each_investigator(game):
                other.resources = max(0, other.resources - 2)
            log("🎒 遭遇：補給短缺——每位调查员失去2资源")
        elif choice == "discard_asset":
            for other in _each_investigator(game):
                # 简化：自动弃掉费用最低的支援（官方由各位调查员选择）
                best = None
                for iid in other.play_area:
                    inst = game.state.get_card_instance(iid)
                    cd = game.state.get_card_data(inst.card_id) if inst else None
                    if cd is None or cd.type.value != "asset":
                        continue
                    if best is None or (cd.cost or 0) < best[0]:
                        best = (cd.cost or 0, iid)
                if best is not None:
                    inst = game.state.cards_in_play.pop(best[1], None)
                    if inst is not None:
                        other.play_area.remove(best[1])
                        other.discard.append(inst.card_id)
                        log(f"  → 【{game.state.card_name(inst.card_id)}】被弃掉")
            log("🎒 遭遇：補給短缺——每位调查员弃掉1张支援")
        else:  # take_damage
            for other in _each_investigator(game):
                game.damage_engine.deal_damage(other.investigator_id, damage=1)
            log("🎒 遭遇：補給短缺——每位调查员受1伤害")
        return {"pending": False, "message": "low_on_supplies"}

    # ---- Agents of Yig ----
    if card_id == "curse_of_yig":
        iid = _place_in_threat(game, inv, "curse_of_yig")
        inv.health_bonus -= 1  # 生命-1（可强制部分）
        # 简化：-1战斗与获得蛇族属性记入 vars，未强制（无技能值修正钩子）
        svars.setdefault("curse_of_yig", {})[investigator_id] = iid
        log("🐍 遭遇：伊格的詛咒——放入威胁区（-1战斗[未强制]、生命-1、获得蛇族属性[未强制]；"
            "可用 activate_curse_of_yig 意志2+每复仇点1弃掉）")
        return {"pending": False, "message": "curse_of_yig"}

    # ---- Guardians of Time ----
    if card_id == "arrows_from_the_trees":
        targets = [inv]
        for other in _each_investigator(game):
            if other.investigator_id == investigator_id:
                continue
            if "ancient" in _location_traits(game, other.location_id) \
                    or "古代" in _location_traits(game, other.location_id):
                targets.append(other)
        for victim in targets:
            n = 1 + len(_ally_assets(game, victim))
            game.damage_engine.deal_damage(victim.investigator_id, damage=n)
            log(f"🏹 遭遇：林中暗箭——【{victim.investigator_id}】受{n}伤害")
        return {"pending": False, "message": "arrows_from_the_trees"}

    # ---- Traps ----
    if card_id == "final_mistake":
        loc = game.state.get_location(inv.location_id)
        difficulty = 2 + (loc.doom if loc is not None else 0)
        log(f"🕳️ 遭遇：致命錯誤（敏捷{difficulty}，失败受2伤害）")
        run_test(investigator_id, skill=Skill.AGILITY, difficulty=difficulty,
                 on_failure=lambda r: game.damage_engine.deal_damage(investigator_id, damage=2))
        return {"pending": False, "message": "final_mistake"}

    if card_id == "entombed":
        iid = _place_in_threat(game, inv, "entombed")
        # 简化：不能解除交战/移动记入 vars，未强制（引擎无拦截钩子）
        svars.setdefault("entombed", {})[investigator_id] = {"instance": iid, "reduction": 0}
        log("🪦 遭遇：半身入土——放入威胁区（不能解除交战/移动[未强制]；"
            "可用 activate_entombed 敏捷/战斗4弃掉，失败本轮难度-1）")
        return {"pending": False, "message": "entombed"}

    # ---- Flux ----
    if card_id == "a_tear_in_time":
        log("⏳ 遭遇：時間裂縫（意志3，失败每点：失去1行动或受1恐惧）")

        def on_fail(r):
            # 简化：自动先失去行动（直至0），其余转为恐惧（官方逐点二选一）
            m = _margin_fail(r)
            lost = min(m, inv.actions_remaining)
            inv.actions_remaining -= lost
            rest = m - lost
            if rest:
                game.damage_engine.deal_damage(investigator_id, horror=rest)
            if lost or rest:
                log(f"  → 失去{lost}行动" + (f"，受{rest}恐惧" if rest else ""))
        run_test(investigator_id, skill=Skill.WILLPOWER, difficulty=3, on_failure=on_fail)
        return {"pending": False, "message": "a_tear_in_time"}

    if card_id == "lost_in_time":
        # 简化：自动选择第一张非剧情支援（官方由你选择）；
        # 剧情支援 = unique 或带 story/劇情 属性
        chosen = None
        for iid in inv.play_area:
            inst = game.state.get_card_instance(iid)
            cd = game.state.get_card_data(inst.card_id) if inst else None
            if cd is None or cd.type.value != "asset":
                continue
            tags = _tags_of_cd(cd)
            if cd.unique or "story" in tags or "劇情" in tags:
                continue
            chosen = (iid, inst)
            break
        if chosen is not None:
            iid, inst = chosen
            moved_damage, moved_horror = inst.damage, inst.horror
            game.state.cards_in_play.pop(iid, None)
            inv.play_area.remove(iid)
            inv.deck.append(inst.card_id)
            random.shuffle(inv.deck)
            if moved_damage or moved_horror:
                game.damage_engine.deal_damage(investigator_id, damage=moved_damage,
                                               horror=moved_horror)
            log(f"⌛ 遭遇：困於時間——【{game.state.card_name(inst.card_id)}】洗回牌堆"
                f"（移动{moved_damage}伤害{moved_horror}恐惧）")
        else:
            # 简化：自动弃前3张（官方由你选择）
            discarded = []
            for cid in list(inv.hand)[:3]:
                inv.hand.remove(cid)
                inv.discard.append(cid)
                discarded.append(cid)
            log(f"⌛ 遭遇：困於時間——无支援可洗回，弃掉3张手牌【{_log_names(game, discarded)}】")
        return {"pending": False, "message": "lost_in_time"}

    # ---- Ruins ----
    if card_id == "ill_omen":
        # 简化：自动选择自己所在地点（官方任选有调查员的地点）
        loc = game.state.get_location(inv.location_id)
        if loc is not None:
            loc.doom += 1
            controller._check_agenda_threshold()
            for other in _each_investigator(game):
                if other.location_id == inv.location_id:
                    game.damage_engine.deal_damage(other.investigator_id, horror=1)
            log(f"🔮 遭遇：不祥之兆——【{game.state.card_name(loc.card_data.id)}】+1毁灭，"
                "该地点每位调查员受1恐惧")
        return {"pending": False, "message": "ill_omen"}

    if card_id == "ancestral_fear":
        if choice is None:
            svars["pending_choice"] = {
                "card_id": card_id,
                "investigator_id": investigator_id,
                "prompt": "先祖恐懼：你必须决定——所在地点+1毁灭并弃掉 或 放入胜利牌区",
                "options": [
                    {"id": "place_doom", "label": "所在地点+1毁灭并弃掉先祖恐懼"},
                    {"id": "victory_display", "label": "将先祖恐懼放入胜利牌区"},
                ],
            }
            return {"pending": True, "message": "pending_choice"}
        if choice == "victory_display":
            game.state.scenario.victory_display.append("ancestral_fear")
            log("😨 遭遇：先祖恐懼——放入胜利牌区，涌动")
        else:
            loc = game.state.get_location(inv.location_id)
            if loc is not None:
                loc.doom += 1
                controller._check_agenda_threshold()
            log("😨 遭遇：先祖恐懼——所在地点+1毁灭，弃掉，涌动")
        return {"pending": False, "message": "surge", "surge": True}

    if card_id == "deep_dark":
        # 简化：每地点每调查员每轮最多发现1线索记入 vars，未强制（无线索发现拦截钩子）
        svars["deep_dark"] = svars.get("deep_dark", 0) + 1
        _round_end_countdown(game, "deep_dark")
        log("🌑 遭遇：一片漆黑——放在密谋旁（每地点每轮限发现1线索[未强制]，轮末弃掉1张）")
        return {"pending": False, "message": "deep_dark"}

    # ---- Pnakotic Brotherhood ----
    if card_id == "shadowed":
        target = _nearest_enemy_with_tag(game, inv, "cultist") \
            or _nearest_enemy_with_tag(game, inv, "異教徒")
        if target is None:
            game.damage_engine.deal_damage(investigator_id, horror=1)
            log("🌫️ 遭遇：陰影籠罩——无异教徒敌人，受1恐惧，涌动")
            return {"pending": False, "message": "surge", "surge": True}
        inst = game.state.get_card_instance(target)
        cd = game.state.get_card_data(inst.card_id) if inst else None
        inst.doom += 1
        controller._check_agenda_threshold()
        x = (cd.enemy_fight or 0) if cd is not None else 0
        log(f"🌫️ 遭遇：陰影籠罩——【{game.state.card_name(inst.card_id)}】+1毁灭（意志{x}，失败受2恐惧）")
        run_test(investigator_id, skill=Skill.WILLPOWER, difficulty=x,
                 on_failure=lambda r: game.damage_engine.deal_damage(investigator_id, horror=2))
        return {"pending": False, "message": "shadowed"}

    if card_id == "words_of_power":
        _place_in_threat(game, inv, "words_of_power")
        # 简化：不能伤害带毁灭敌人/发现线索记入 vars，未强制（无对应钩子）
        svars.setdefault("words_of_power", {})[investigator_id] = True
        log("📜 遭遇：力量真言——放入威胁区（限制未强制；可用 activate_words_of_power 花2行动弃掉）")
        return {"pending": False, "message": "words_of_power"}

    # ---- Venom ----
    if card_id == "snakescourge":
        _place_in_threat(game, inv, "snakescourge")
        # 简化：非弱点道具支援文本框空白记入 vars，未强制（无文本框钩子）
        svars.setdefault("snakescourge", {})[investigator_id] = True

        def _on_round_end(_ctx):
            iid = _threat_copy(game, inv, "snakescourge")
            if iid is not None:
                _remove_from_threat(game, inv, iid)
            svars.get("snakescourge", {}).pop(investigator_id, None)
            log("🐍 毒蛇災厄：本轮结束，弃掉")

        _register_one_shot(game, GameEvent.ROUND_ENDS, _on_round_end)
        if _is_poisoned(game, inv):
            log("🐍 遭遇：毒蛇災厄——放入威胁区（道具文本空白[未强制]，轮末弃掉）；已中毒，涌动")
            return {"pending": False, "message": "surge", "surge": True}
        log("🐍 遭遇：毒蛇災厄——放入威胁区（道具文本空白[未强制]，轮末弃掉）")
        return {"pending": False, "message": "snakescourge"}

    if card_id == "serpents_call":
        if choice is None:
            svars["pending_choice"] = {
                "card_id": card_id,
                "investigator_id": investigator_id,
                "prompt": "毒蛇召來：你必须决定——中毒弱点放入威胁区 或 抽遭遇牌堆顶2张",
                "options": [
                    {"id": "poisoned", "label": "将中毒弱点放入你的威胁区"},
                    {"id": "draw_encounter", "label": "抽取遭遇牌堆顶2张"},
                ],
            }
            return {"pending": True, "message": "pending_choice"}
        if choice == "draw_encounter":
            s = game.state.scenario
            drawn = []
            for _ in range(2):
                if not s.encounter_deck:
                    break
                cid = s.encounter_deck.pop(0)
                drawn.append(cid)
                controller.resolve_encounter_card(cid, investigator_id=investigator_id)
                cd = game.state.get_card_data(cid)
                if cd is None or cd.type.value != "enemy":
                    s.encounter_discard.append(cid)
            log(f"🐍 遭遇：毒蛇召來——抽取遭遇牌堆顶2张【{_log_names(game, drawn)}】")
        else:
            if _put_poisoned(game, inv):
                log("🐍 遭遇：毒蛇召來——中毒弱点放入威胁区")
            else:
                log("🐍 遭遇：毒蛇召來——已中毒，无效果")
        return {"pending": False, "message": "serpents_call"}

    # ---- Poison ----
    if card_id == "creeping_poison":
        for other in _each_investigator(game):
            if _is_poisoned(game, other):
                game.damage_engine.deal_damage(other.investigator_id, damage=1)
                log(f"☠️ 遭遇：毒性蔓延——【{other.investigator_id}】中毒，受1伤害")
        log("☠️ 遭遇：毒性蔓延——涌动")
        return {"pending": False, "message": "surge", "surge": True}

    if card_id == "poisoned":
        # 中毒弱点本体：永久，放入威胁区（被直接抽取/结算时）
        if _put_poisoned(game, inv):
            log("☠️ 遭遇：中毒——弱点放入威胁区（你已中毒）")
        else:
            log("☠️ 遭遇：中毒——已中毒（限1），无效果")
        return {"pending": False, "message": "poisoned"}

    # ---- Threads of Fate ----
    if card_id == "the_secret_must_be_kept":
        x = game.state.scenario.current_act_index  # 已完成的场景牌堆数
        log(f"🤫 遭遇：密不可洩（意志{3 + x}，失败受{1 + x}伤害+{1 + x}恐惧）")
        run_test(investigator_id, skill=Skill.WILLPOWER, difficulty=3 + x,
                 on_failure=lambda r: game.damage_engine.deal_damage(
                     investigator_id, damage=1 + x, horror=1 + x))
        return {"pending": False, "message": "the_secret_must_be_kept"}

    if card_id == "nobodys_home":
        loc = game.state.get_location(inv.location_id)
        no_clues = loc is not None and loc.clues <= 0
        controller.attach_card_to_location("nobodys_home", inv.location_id)
        # 简化：调查+1行动记入 vars，未强制（无行动费用钩子）
        svars.setdefault("nobodys_home", {})[inv.location_id] = True
        if no_clues:
            # 强制：被叠加地点无线索 → 立即弃掉（ RAW：条件即刻满足）
            iid = controller.location_attachment_instance(inv.location_id, "nobodys_home")
            if iid is not None:
                controller.detach_card_from_location(iid)
            svars.get("nobodys_home", {}).pop(inv.location_id, None)
            log("🏠 遭遇：屋中無人——所在地点无线索，涌动并立即弃掉")
            return {"pending": False, "message": "surge", "surge": True}

        holder: list[Any] = []
        attached_loc = inv.location_id

        def _on_clue(_ctx):
            iid = controller.location_attachment_instance(attached_loc, "nobodys_home")
            if iid is None:
                game.event_bus.unregister(holder[0])
                return
            loc2 = game.state.get_location(attached_loc)
            if loc2 is not None and loc2.clues <= 0:
                controller.detach_card_from_location(iid)
                svars.get("nobodys_home", {}).pop(attached_loc, None)
                game.event_bus.unregister(holder[0])
                log("🏠 屋中無人：被叠加地点无线索，弃掉")

        holder.append(game.event_bus.register(GameEvent.CLUE_DISCOVERED, _on_clue,
                                              priority=TimingPriority.AFTER))
        log("🏠 遭遇：屋中無人——叠加到所在地点（调查+1行动[未强制]；无线索时弃掉）")
        return {"pending": False, "message": "nobodys_home"}

    if card_id == "conspiracy_of_blood":
        # 简化：叠加到当前密谋记入 vars；-1毁灭阈值未强制（effective_doom_threshold
        # 为只读属性，引擎缺口）。异教徒获得的谈判能力见 activate_conspiracy_of_blood
        svars["conspiracy_of_blood"] = svars.get("conspiracy_of_blood", 0) + 1
        log("🩸 遭遇：鮮血陰謀——叠加到当前密谋（密谋阈值-1[未强制]；"
            "可用 activate_conspiracy_of_blood 对异教徒谈判意志4弃掉）")
        return {"pending": False, "message": "conspiracy_of_blood"}

    # ---- The Boundary Beyond ----
    if card_id == "window_to_another_time":
        ancients = _locations_with_trait(game, "ancient") or _locations_with_trait(game, "古代")
        if choice is None:
            options = [{"id": "place_doom", "label": "当前密谋+1毁灭（可能推进）"}]
            if ancients:
                options.insert(0, {"id": "shuffle_location",
                                   "label": "将1个古代地点洗回探索牌堆"})
            svars["pending_choice"] = {
                "card_id": card_id,
                "investigator_id": investigator_id,
                "prompt": "異時空之窗：你必须决定——古代地点洗回探索牌堆 或 当前密谋+1毁灭",
                "options": options,
            }
            return {"pending": True, "message": "pending_choice"}
        if choice == "shuffle_location" and ancients:
            # 简化：自动选择第一个古代地点；其下的现代地点取而代之——
            # 引擎无地点配对数据，移除记录于 vars["returned_to_exploration"]
            lid = ancients[0]
            loc = game.state.locations.pop(lid, None)
            if loc is not None:
                _shuffle_into_exploration_deck(game, loc.card_data.id)
                svars.setdefault("returned_to_exploration", []).append(lid)
                log(f"🪟 遭遇：異時空之窗——【{game.state.card_name(loc.card_data.id)}】洗回探索牌堆")
        else:
            game.state.scenario.doom_on_agenda += 1
            controller._check_agenda_threshold()
            log("🪟 遭遇：異時空之窗——当前密谋+1毁灭")
        return {"pending": False, "message": "window_to_another_time"}

    if card_id == "timeline_destabilization":
        n = len(_locations_with_trait(game, "ancient") or _locations_with_trait(game, "古代"))
        log(f"⏰ 遭遇：時間線失穩（意志{1 + n}，失败受1伤害+1恐惧并洗回探索牌堆）")

        def on_fail(_r):
            game.damage_engine.deal_damage(investigator_id, damage=1, horror=1)
            _shuffle_into_exploration_deck(game, "timeline_destabilization")
            log("  → 時間線失穩洗回探索牌堆")
        run_test(investigator_id, skill=Skill.WILLPOWER, difficulty=1 + n, on_failure=on_fail)
        return {"pending": False, "message": "timeline_destabilization"}

    # ---- Heart of the Elders ----
    if card_id == "pitfall":
        if choice is None:
            # 简化：不追踪"是否抽自探索牌堆"，两个选项始终可用
            svars["pending_choice"] = {
                "card_id": card_id,
                "investigator_id": investigator_id,
                "prompt": "落入陷阱：你必须决定——敏捷3跳过缺口（失败每点受1伤）或洗回探索牌堆",
                "options": [
                    {"id": "test_agility", "label": "检定敏捷3（失败每点受1伤害）"},
                    {"id": "shuffle_back", "label": "将落入陷阱洗回探索牌堆"},
                ],
            }
            return {"pending": True, "message": "pending_choice"}
        if choice == "shuffle_back":
            _shuffle_into_exploration_deck(game, "pitfall")
            log("🕳️ 遭遇：落入陷阱——洗回探索牌堆")
        else:
            log("🕳️ 遭遇：落入陷阱（敏捷3，失败每点受1伤害）")
            run_test(investigator_id, skill=Skill.AGILITY, difficulty=3,
                     on_failure=lambda r: game.damage_engine.deal_damage(
                         investigator_id, damage=_margin_fail(r)))
        return {"pending": False, "message": "pitfall"}

    if card_id == "poisonous_spores":
        controller.attach_card_to_location("poisonous_spores", inv.location_id)
        attached_loc = inv.location_id

        def _on_round_end(_ctx):
            for other in _each_investigator(game):
                if other.location_id != attached_loc:
                    continue
                if _is_poisoned(game, other):
                    game.damage_engine.deal_damage(other.investigator_id, horror=2)
                    log(f"🍄 有毒孢子：【{other.investigator_id}】已中毒，受2恐惧")
                elif _put_poisoned(game, other):
                    log(f"🍄 有毒孢子：【{other.investigator_id}】中毒弱点放入威胁区")
            iid = controller.location_attachment_instance(attached_loc, "poisonous_spores")
            if iid is not None:
                controller.detach_card_from_location(iid)
            log("🍄 有毒孢子：本轮结束，弃掉")

        _register_one_shot(game, GameEvent.ROUND_ENDS, _on_round_end)
        log("🍄 遭遇：有毒孢子——叠加到所在地点（轮末结算中毒，然后弃掉）")
        return {"pending": False, "message": "poisonous_spores"}

    # ---- Pillars of Judgment ----
    if card_id == "ants":
        log("🐜 遭遇：蟻群纏身（敏捷4，失败每点：随机弃1手牌或弃1场上卡）")

        def on_fail(r):
            # 简化：自动先随机弃手牌，手牌为空后弃场上第一张（官方二选一）
            for _ in range(_margin_fail(r)):
                if inv.hand:
                    cid = random.choice(inv.hand)
                    inv.hand.remove(cid)
                    inv.discard.append(cid)
                    log(f"  → 随机弃掉手牌【{game.state.card_name(cid)}】")
                elif inv.play_area:
                    iid = inv.play_area[0]
                    inst = game.state.cards_in_play.pop(iid, None)
                    if inst is not None:
                        inv.play_area.remove(iid)
                        inv.discard.append(inst.card_id)
                        log(f"  → 弃掉【{game.state.card_name(inst.card_id)}】")
        run_test(investigator_id, skill=Skill.AGILITY, difficulty=4, on_failure=on_fail)
        return {"pending": False, "message": "ants"}

    # ---- K'n-yan ----
    if card_id == "no_turning_back":
        # 简化：自动叠加到自己所在地点（官方可选相连地点）；每地点限1
        if controller.location_with_attachment("no_turning_back") is not None:
            log("🚧 遭遇：無路可退——已有在场（限1），弃掉")
            return {"pending": False, "message": "no_turning_back"}
        controller.attach_card_to_location("no_turning_back", inv.location_id)
        # 简化：不能进入/离开记入 vars，未强制（引擎无移动拦截钩子）
        svars.setdefault("no_turning_back", {})[inv.location_id] = True
        log("🚧 遭遇：無路可退——叠加到所在地点（不能进入/离开[未强制]；"
            "可用 activate_no_turning_back 战斗3或铁镐弃掉）")
        return {"pending": False, "message": "no_turning_back"}

    # ---- The City of Archives ----
    if card_id == "yithian_presence":
        _place_in_threat(game, inv, "yithian_presence")
        # 简化：不能调查/触发遭遇卡行动能力记入 vars，未强制（无对应钩子）
        svars.setdefault("yithian_presence", {})[investigator_id] = True
        log("👽 遭遇：伊斯人登場——放入威胁区（限制未强制；"
            "可用 activate_yithian_presence 弃2手牌弃掉）")
        return {"pending": False, "message": "yithian_presence"}

    if card_id == "cruel_interrogations":
        _place_in_threat(game, inv, "cruel_interrogations")
        # 简化：不能执行抽牌行动记入 vars，未强制（无对应钩子）
        svars.setdefault("cruel_interrogations", {})[investigator_id] = True
        interviewed = int(svars.get("interviewed_subjects", 0) or 0) > 0
        if interviewed:
            game.damage_engine.deal_damage(investigator_id, horror=1)
            log("🔪 遭遇：殘酷拷問——已访谈过对象，受1恐惧，涌动"
                "（不能抽牌[未强制]；可用 activate_cruel_interrogations 意志2弃掉）")
            return {"pending": False, "message": "surge", "surge": True}
        log("🔪 遭遇：殘酷拷問——放入威胁区（不能抽牌[未强制]；"
            "可用 activate_cruel_interrogations 意志2弃掉）")
        return {"pending": False, "message": "cruel_interrogations"}

    if card_id == "lost_humanity":
        log("🧠 遭遇：喪失人性（意志5，失败每点移除牌堆顶1张；卡牌<10则发疯）")

        def on_fail(r):
            m = _margin_fail(r)
            removed = svars.setdefault("removed_from_game", [])
            for _ in range(m):
                if inv.deck:
                    removed.append(inv.deck.pop(0))
            total = len(inv.hand) + len(inv.deck) + len(inv.discard)
            if total < 10:
                # 简化：发疯按退场处理（恐惧拉满走 defeat 管线），并记录 vars 标记
                inv.horror = inv.sanity
                insane = svars.setdefault("insane_investigators", [])
                if investigator_id not in insane:
                    insane.append(investigator_id)
                log("🧠 喪失人性：卡牌不足10张，调查员发疯（退场）")
                game.damage_engine._check_defeat(investigator_id)
        run_test(investigator_id, skill=Skill.WILLPOWER, difficulty=5, on_failure=on_fail)
        return {"pending": False, "message": "lost_humanity"}

    if card_id == "captive_mind":
        log("🧠 遭遇：被監禁的意識（意志0；无论成败，手牌弃到剩X=修正后技能值）")

        def _settle(r):
            x = max(0, getattr(r, "modified_skill", 0) or 0)
            # 简化：自动保留前X张（官方由你选择保留哪些）
            while len(inv.hand) > x:
                cid = inv.hand.pop()
                inv.discard.append(cid)
                log(f"  → 弃掉【{game.state.card_name(cid)}】")
        _run_test_full(controller, investigator_id, skill=Skill.WILLPOWER, difficulty=0,
                       on_success=_settle, on_failure=_settle)
        return {"pending": False, "message": "captive_mind"}

    if card_id == "out_of_body_experience":
        n = len(inv.hand)
        inv.deck.extend(inv.hand)
        inv.hand.clear()
        random.shuffle(inv.deck)
        drawn = []
        for _ in range(n):
            if inv.deck:
                drawn.append(inv.deck.pop(0))
        inv.hand.extend(drawn)
        inv.deck.append("out_of_body_experience")
        random.shuffle(inv.deck)
        log(f"👻 遭遇：離體體驗——{n}张手牌洗回牌堆并抽取{n}张，離體體驗洗入牌堆")
        return {"pending": False, "message": "out_of_body_experience"}

    # ---- The Depths of Yoth ----
    if card_id == "children_of_valusia":
        # 简化：蛇族敌人+1战斗/+1躲避记入 vars，未强制（无敌人数值修正钩子）
        svars["children_of_valusia"] = svars.get("children_of_valusia", 0) + 1
        _round_end_countdown(game, "children_of_valusia")
        log("🐍 遭遇：瓦盧西亞之子——放在密谋旁（蛇族+1战斗/+1躲避[未强制]，轮末弃掉1张）")
        return {"pending": False, "message": "children_of_valusia"}

    if card_id == "lightless_shadow":
        x = _depth(game)
        log(f"🌑 遭遇：無光之影（敏捷{1 + x}，失败受2伤害）")
        run_test(investigator_id, skill=Skill.AGILITY, difficulty=1 + x,
                 on_failure=lambda r: game.damage_engine.deal_damage(investigator_id, damage=2))
        return {"pending": False, "message": "lightless_shadow"}

    if card_id == "bathophobia":
        x = _depth(game)
        log(f"🕳️ 遭遇：深淵恐懼症（意志{1 + x}，失败受2恐惧）")
        run_test(investigator_id, skill=Skill.WILLPOWER, difficulty=1 + x,
                 on_failure=lambda r: game.damage_engine.deal_damage(investigator_id, horror=2))
        return {"pending": False, "message": "bathophobia"}

    if card_id == "serpents_ire":
        # 简化：追击中敌人 = vars["in_pursuit"]（引擎无追击区，由剧本层维护）
        pursuit = svars.get("in_pursuit", []) or []
        serpents = []
        for cid in pursuit:
            cd = game.state.get_card_data(cid)
            if cd is not None and cd.type.value == "enemy" and "serpent" in _tags_of_cd(cd):
                serpents.append((cd.enemy_fight or 0, cid))
        if not serpents:
            log("🐍 遭遇：蛇族的憤怒——无追击中的蛇族敌人，涌动")
            return {"pending": False, "message": "surge", "surge": True}
        serpents.sort(key=lambda t: t[0], reverse=True)
        fight, chosen = serpents[0]
        pursuit.remove(chosen)
        iid = _place_in_threat(game, inv, chosen)
        log(f"🐍 遭遇：蛇族的憤怒——【{game.state.card_name(chosen)}】生成并与你交战"
            f"（敏捷{fight}，失败它立即攻击）")

        def on_fail(_r):
            _enemy_attack(game, iid, investigator_id)
            log("  → 立即攻击你")
        run_test(investigator_id, skill=Skill.AGILITY, difficulty=fight, on_failure=on_fail)
        return {"pending": False, "message": "serpents_ire"}

    # ---- Shattered Aeons ----
    if card_id == "shattered_ages":
        log("⏳ 遭遇：破碎的時代（意志4，失败每个非 Nexus of N'kai 地点+1线索）")

        def on_fail(_r):
            nexus = _nexus_location_id(game)
            for loc in game.state.locations.values():
                if loc.location_id == nexus:
                    continue
                loc.clues += 1
        run_test(investigator_id, skill=Skill.WILLPOWER, difficulty=4, on_failure=on_fail)
        return {"pending": False, "message": "shattered_ages"}

    if card_id == "between_worlds":
        # 简化：以合成地点卡入场（3隐蔽/1线索/异世界属性），连接到 Nexus of N'kai
        nexus = _nexus_location_id(game)
        loc_id = "between_worlds"
        if loc_id not in game.state.locations:
            cd = CardData(
                id="between_worlds", name="Between Worlds", name_cn="異界之間",
                type=CardType.LOCATION, shroud=3, clue_value=1, traits=["otherworld"],
                connections=[nexus] if nexus else [],
            )
            game.register_card_data(cd)
            loc = game.add_location(loc_id, cd, clues=1)
            loc.revealed = True
        inv.location_id = loc_id

        holder: list[Any] = []

        def _on_round_end(_ctx):
            loc = game.state.get_location(loc_id)
            if loc is None:
                game.event_bus.unregister(holder[0])
                return
            here = [o for o in _each_investigator(game) if o.location_id == loc_id]
            if here:
                for other in here:
                    game.damage_engine.deal_damage(other.investigator_id, damage=1, horror=1)
                log("🌌 異界之間：本轮结束——此处每位调查员受1伤害+1恐惧")
                return
            # 无人：弃掉地点，敌人移到 Nexus of N'kai
            nexus_id = _nexus_location_id(game)
            nexus_loc = game.state.get_location(nexus_id) if nexus_id else None
            if nexus_loc is not None:
                for e in list(loc.enemies):
                    loc.enemies.remove(e)
                    nexus_loc.enemies.append(e)
            game.state.locations.pop(loc_id, None)
            game.event_bus.unregister(holder[0])
            log("🌌 異界之間：此处无人，弃掉地点（敌人移至 Nexus of N'kai）")

        holder.append(game.event_bus.register(GameEvent.ROUND_ENDS, _on_round_end,
                                              priority=TimingPriority.AFTER))
        log("🌌 遭遇：異界之間——作为3隐蔽1线索地点入场并移动到该处（轮末此处每人受1伤1恐）")
        return {"pending": False, "message": "between_worlds"}

    if card_id == "wracked_by_time":
        log("⏰ 遭遇：時空撕裂（意志3，失败受2伤害；因此受伤的未败支援洗回牌主牌堆）")

        def _settle_for(target_inv):
            def on_fail(_r):
                game.damage_engine.deal_damage(target_inv.investigator_id, damage=2)
                # 简化：伤害引擎默认分配给调查员本人；此处按"场上带伤的未败
                # 支援"近似处理被分配伤害的支援（官方仅指本效果分配的）
                for iid in list(target_inv.play_area):
                    inst = game.state.get_card_instance(iid)
                    if inst is None or inst.damage <= 0:
                        continue
                    game.state.cards_in_play.pop(iid, None)
                    target_inv.play_area.remove(iid)
                    target_inv.deck.append(inst.card_id)
                    log(f"  → 带伤的【{game.state.card_name(inst.card_id)}】洗回牌堆")
                random.shuffle(target_inv.deck)
            return on_fail

        run_test(investigator_id, skill=Skill.WILLPOWER, difficulty=3,
                 on_failure=_settle_for(inv))
        # 简化：破碎地点判定看地点属性 shattered/破碎
        for other in _each_investigator(game):
            if other.investigator_id == investigator_id:
                continue
            traits = _location_traits(game, other.location_id)
            if "shattered" in traits or "破碎" in traits:
                run_test(other.investigator_id, skill=Skill.WILLPOWER, difficulty=3,
                         on_failure=_settle_for(other))
        return {"pending": False, "message": "wracked_by_time"}

    if card_id == "creeping_darkness":
        # 简化：无 Nexus of N'kai 时叠加到自己所在地点
        target_loc = _nexus_location_id(game) or inv.location_id
        iid = controller.attach_card_to_location("creeping_darkness", target_loc)
        inst = game.state.get_card_instance(iid) if iid else None
        if inst is not None:
            inst.doom += 1
        controller._check_agenda_threshold()
        # 简化：无形之雾 +1♟生命记入 vars，未强制（无敌人生命修正钩子）
        svars["creeping_darkness"] = svars.get("creeping_darkness", 0) + 1
        log("🌑 遭遇：黑暗隱伏——叠加到 Nexus of N'kai 并+1毁灭（无形之雾+1生命[未强制]；"
            "可用 activate_creeping_darkness 花2行动意志3或火把弃掉）")
        return {"pending": False, "message": "creeping_darkness"}

    return None


# ---------------------------------------------------------------------------
# 公开激活方法（持续卡的 [行动] 能力；供 session 层/测试调用）
# ---------------------------------------------------------------------------


def activate_overgrowth(controller, investigator_id: str, skill: str = "combat") -> bool:
    """[行动]：检定战斗(4)或智力(4)，成功弃掉所在地点的瘋狂生長。"""
    game = controller.game
    inv = game.state.get_investigator(investigator_id)
    if inv is None or inv.actions_remaining < 1:
        return False
    iid = controller.location_attachment_instance(inv.location_id, "overgrowth")
    if iid is None:
        return False
    inv.actions_remaining -= 1
    sk = Skill.INTELLECT if skill == "intellect" else Skill.COMBAT

    def _ok(_r):
        controller.detach_card_from_location(iid)
        game.state.scenario.vars.get("overgrowth", {}).pop(inv.location_id, None)
        controller.log("🌿 检定成功：弃掉【瘋狂生長】")

    _run_test_full(controller, investigator_id, skill=sk, difficulty=4, on_success=_ok)
    return True


def activate_voice_of_the_jungle(controller, investigator_id: str) -> bool:
    """[行动]：检定意志(3)，成功弃掉威胁区的叢林之聲。"""
    game = controller.game
    inv = game.state.get_investigator(investigator_id)
    if inv is None or inv.actions_remaining < 1:
        return False
    iid = _threat_copy(game, inv, "voice_of_the_jungle")
    if iid is None:
        return False
    inv.actions_remaining -= 1

    def _ok(_r):
        _remove_from_threat(game, inv, iid)
        game.state.scenario.vars.get("voice_of_the_jungle", {}).pop(investigator_id, None)
        controller.log("🌴 检定成功：弃掉【叢林之聲】")

    _run_test_full(controller, investigator_id, skill=Skill.WILLPOWER, difficulty=3,
                   on_success=_ok)
    return True


def activate_curse_of_yig(controller, investigator_id: str) -> bool:
    """[行动]：检定意志(2+胜利牌区复仇点数)，成功弃掉伊格的詛咒。"""
    game = controller.game
    inv = game.state.get_investigator(investigator_id)
    if inv is None or inv.actions_remaining < 1:
        return False
    iid = _threat_copy(game, inv, "curse_of_yig")
    if iid is None:
        return False
    inv.actions_remaining -= 1
    difficulty = 2 + _vengeance_points(game)

    def _ok(_r):
        _remove_from_threat(game, inv, iid)
        inv.health_bonus += 1  # 恢复生命-1
        game.state.scenario.vars.get("curse_of_yig", {}).pop(investigator_id, None)
        controller.log("🐍 检定成功：弃掉【伊格的詛咒】（生命恢复）")

    _run_test_full(controller, investigator_id, skill=Skill.WILLPOWER,
                   difficulty=difficulty, on_success=_ok)
    return True


def activate_entombed(controller, investigator_id: str, skill: str = "agility") -> bool:
    """[行动]：检定敏捷(4)或战斗(4)。成功弃掉半身入土；失败本轮该检定难度-1。"""
    game = controller.game
    inv = game.state.get_investigator(investigator_id)
    if inv is None or inv.actions_remaining < 1:
        return False
    rec = game.state.scenario.vars.get("entombed", {}).get(investigator_id)
    iid = _threat_copy(game, inv, "entombed")
    if rec is None or iid is None:
        return False
    inv.actions_remaining -= 1
    sk = Skill.COMBAT if skill == "combat" else Skill.AGILITY
    difficulty = max(0, 4 - int(rec.get("reduction", 0) or 0))

    def _ok(_r):
        _remove_from_threat(game, inv, iid)
        game.state.scenario.vars.get("entombed", {}).pop(investigator_id, None)
        controller.log("🪦 检定成功：弃掉【半身入土】")

    def _fail(_r):
        rec["reduction"] = int(rec.get("reduction", 0) or 0) + 1
        _register_one_shot(game, GameEvent.ROUND_ENDS,
                           lambda _ctx: rec.__setitem__("reduction", 0))
        controller.log("🪦 检定失败：本轮内该检定难度-1")

    _run_test_full(controller, investigator_id, skill=sk, difficulty=difficulty,
                   on_success=_ok, on_failure=_fail)
    return True


def activate_words_of_power(controller, investigator_id: str) -> bool:
    """[行动][行动]：弃掉威胁区的力量真言。"""
    game = controller.game
    inv = game.state.get_investigator(investigator_id)
    if inv is None or inv.actions_remaining < 2:
        return False
    iid = _threat_copy(game, inv, "words_of_power")
    if iid is None:
        return False
    inv.actions_remaining -= 2
    _remove_from_threat(game, inv, iid)
    game.state.scenario.vars.get("words_of_power", {}).pop(investigator_id, None)
    controller.log("📜 花2行动弃掉【力量真言】")
    return True


def activate_conspiracy_of_blood(controller, investigator_id: str,
                                 enemy_instance_id: str) -> bool:
    """[行动] 谈判：对1个异教徒敌人检定意志(4)。成功弃掉1张鮮血陰謀；失败该敌人+1毁灭。"""
    game = controller.game
    inv = game.state.get_investigator(investigator_id)
    if inv is None or inv.actions_remaining < 1:
        return False
    if game.state.scenario.vars.get("conspiracy_of_blood", 0) <= 0:
        return False
    tags = _tags_of(game, enemy_instance_id)
    if "cultist" not in tags and "異教徒" not in tags:
        return False
    inv.actions_remaining -= 1

    def _ok(_r):
        left = game.state.scenario.vars.get("conspiracy_of_blood", 0)
        if left <= 1:
            game.state.scenario.vars.pop("conspiracy_of_blood", None)
        else:
            game.state.scenario.vars["conspiracy_of_blood"] = left - 1
        controller.log("🩸 谈判成功：弃掉1张【鮮血陰謀】")

    def _fail(_r):
        inst = game.state.get_card_instance(enemy_instance_id)
        if inst is not None:
            inst.doom += 1
            controller._check_agenda_threshold()
        controller.log("🩸 谈判失败：该异教徒+1毁灭")

    _run_test_full(controller, investigator_id, skill=Skill.WILLPOWER, difficulty=4,
                   on_success=_ok, on_failure=_fail)
    return True


def activate_no_turning_back(controller, investigator_id: str) -> bool:
    """[行动]：检定战斗(3)；若补给中有铁镐（pickaxe）则直接弃掉無路可退。

    简化：任何调查员都可激活（官方限被叠加地点及相连地点的调查员）。
    """
    game = controller.game
    inv = game.state.get_investigator(investigator_id)
    if inv is None or inv.actions_remaining < 1:
        return False
    loc_id = controller.location_with_attachment("no_turning_back")
    if loc_id is None:
        return False
    inv.actions_remaining -= 1
    iid = controller.location_attachment_instance(loc_id, "no_turning_back")

    def _discard():
        controller.detach_card_from_location(iid)
        game.state.scenario.vars.get("no_turning_back", {}).pop(loc_id, None)
        controller.log("🚧 弃掉【無路可退】")

    if "pickaxe" in _supplies(game, investigator_id):
        _discard()
        return True
    _run_test_full(controller, investigator_id, skill=Skill.COMBAT, difficulty=3,
                   on_success=lambda _r: _discard())
    return True


def activate_yithian_presence(controller, investigator_id: str) -> bool:
    """[行动] 选择并弃掉2张手牌：弃掉伊斯人登場。简化：自动弃前2张。"""
    game = controller.game
    inv = game.state.get_investigator(investigator_id)
    if inv is None or inv.actions_remaining < 1 or len(inv.hand) < 2:
        return False
    iid = _threat_copy(game, inv, "yithian_presence")
    if iid is None:
        return False
    inv.actions_remaining -= 1
    for cid in list(inv.hand)[:2]:
        inv.hand.remove(cid)
        inv.discard.append(cid)
    _remove_from_threat(game, inv, iid)
    game.state.scenario.vars.get("yithian_presence", {}).pop(investigator_id, None)
    controller.log("👽 花1行动弃2手牌：弃掉【伊斯人登場】")
    return True


def activate_cruel_interrogations(controller, investigator_id: str) -> bool:
    """[行动]：检定意志(2)，成功弃掉殘酷拷問。"""
    game = controller.game
    inv = game.state.get_investigator(investigator_id)
    if inv is None or inv.actions_remaining < 1:
        return False
    iid = _threat_copy(game, inv, "cruel_interrogations")
    if iid is None:
        return False
    inv.actions_remaining -= 1

    def _ok(_r):
        _remove_from_threat(game, inv, iid)
        game.state.scenario.vars.get("cruel_interrogations", {}).pop(investigator_id, None)
        controller.log("🔪 检定成功：弃掉【殘酷拷問】")

    _run_test_full(controller, investigator_id, skill=Skill.WILLPOWER, difficulty=2,
                   on_success=_ok)
    return True


def activate_creeping_darkness(controller, investigator_id: str) -> bool:
    """[行动][行动]：检定意志(3)；若补给中有火把（torches）则直接弃掉黑暗隱伏。"""
    game = controller.game
    inv = game.state.get_investigator(investigator_id)
    if inv is None or inv.actions_remaining < 2:
        return False
    loc_id = controller.location_with_attachment("creeping_darkness")
    if loc_id is None:
        return False
    inv.actions_remaining -= 2
    iid = controller.location_attachment_instance(loc_id, "creeping_darkness")

    def _discard():
        controller.detach_card_from_location(iid)
        left = game.state.scenario.vars.get("creeping_darkness", 0)
        if left <= 1:
            game.state.scenario.vars.pop("creeping_darkness", None)
        else:
            game.state.scenario.vars["creeping_darkness"] = left - 1
        controller.log("🌑 弃掉【黑暗隱伏】")

    if "torches" in _supplies(game, investigator_id):
        _discard()
        return True
    _run_test_full(controller, investigator_id, skill=Skill.WILLPOWER, difficulty=3,
                   on_success=lambda _r: _discard())
    return True
