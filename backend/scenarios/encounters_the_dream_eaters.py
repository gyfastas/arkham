"""The Dream-Eaters encounter treachery resolution.

Called from ScenarioController.resolve_encounter_card as a fallback after the
Dunwich branch (wiring done by the session layer). Each handler returns
{"pending": bool, "message": str} (plus "surge": True when the card gains
surge) or None (to continue to the next matcher). Choice cards set
`scenario.vars["pending_choice"]` (with an "investigator_id" field for
multiplayer routing) and are re-entered with `choice=<option_id>`.

Simplifications (documented per card below):

- Hidden/Peril cards (law_of_ygiroth_a-c, whispering_chaos_a-d,
  restless_journey_a-c): the digital version cannot keep secrets, so the card
  is added to the hand openly. Ongoing restrictions are recorded in
  `scenario.vars` and NOT enforced by the engine (no hook points); each
  card's discard ability is exposed as a public `activate_*` function in this
  module for the session layer / tests to call.
- "You must either X or Y" choices inside failed skill tests resolve
  deterministically (documented per card); the only revelation-time choice
  using pending_choice is whispers_of_hypnos (which skill to weaken).
- Scenario-specific subsystems with no engine support are recorded in
  `scenario.vars` only: infestation tests (waking_nightmare), alarm levels
  (dark_side_of_the_moon, stored in vars["alarm_level"]), the pitch location
  line (a_thousand_shapes_of_horror, vars["pitch_locations"]), tower
  abilities (where_the_gods_dwell), scenario reference card damage
  (descent_into_the_pitch, vars["scenario_reference_damage"]).
- Trait/keyword checks scan both `keywords` and `traits` (TDE data stores
  English traits; tests set keywords directly).
- ArkhamDB was unreachable at implementation time; card text is taken from
  data/encounter_cards/the_dream_eaters.json (itself generated from
  arkhamdb + zh.arkhamdb).
"""

from __future__ import annotations

import random
from typing import Any

from backend.models.enums import GameEvent, Skill, TimingPriority
from backend.models.state import CardInstance, is_weakness_card

# ---------------------------------------------------------------------------
# Hidden/持续卡限制标记（scenario.vars 记录；引擎暂无拦截点，未强制）
# ---------------------------------------------------------------------------

# 伊吉若斯之理：偶数条件（用于 [行动] 弃牌）；持续限制说明
_LAW_OF_YGIROTH = {
    "law_of_ygiroth_a": "no_odd_cost_play",      # 不能打出/触发奇数印刷费用的玩家卡
    "law_of_ygiroth_b": "no_odd_icon_commit",    # 不能投入技能图标总数为奇数的卡
    "law_of_ygiroth_c": "no_odd_word_commit",    # 不能打出/投入标题词数为奇数的卡
}

# 无眠之旅：各版本 [fast] 弃牌时的检定技能
_RESTLESS_JOURNEY_SKILL = {
    "restless_journey_a": Skill.INTELLECT,
    "restless_journey_b": Skill.COMBAT,
    "restless_journey_c": Skill.AGILITY,
}

# 混沌低语：各版本对应的方塔（where_the_gods_dwell 剧本机制，未实现）
_WHISPERING_CHAOS_TOWER = {
    "whispering_chaos_a": "北塔",
    "whispering_chaos_b": "东塔",
    "whispering_chaos_c": "南塔",
    "whispering_chaos_d": "西塔",
}


# ---------------------------------------------------------------------------
# 通用辅助
# ---------------------------------------------------------------------------

def _margin_fail(result) -> int:
    return max(0, (getattr(result, "difficulty", 0) or 0) - (getattr(result, "modified_skill", 0) or 0))


def _log_names(game, cids: list[str]) -> str:
    return "、".join(game.state.card_name(c) for c in cids)


def _tags_of(game, instance_id: str) -> list[str]:
    """Enemy keyword+trait union (TDE data keeps English traits)."""
    inst = game.state.get_card_instance(instance_id)
    if inst is None:
        return []
    cd = game.state.get_card_data(inst.card_id)
    if cd is None:
        return []
    return list(getattr(cd, "keywords", None) or []) + list(getattr(cd, "traits", None) or [])


def _is_enemy_with_tag(game, card_id: str, tag: str) -> bool:
    cd = game.state.get_card_data(card_id)
    if cd is None or cd.type.value != "enemy":
        return False
    return tag in list(getattr(cd, "keywords", None) or []) + list(getattr(cd, "traits", None) or [])


def _enemies_with_tag(game, tag: str) -> list[str]:
    out = []
    for iid, inst in game.state.cards_in_play.items():
        cd = game.state.get_card_data(inst.card_id)
        if cd is None or cd.type.value != "enemy":
            continue
        if tag in _tags_of(game, iid):
            out.append(iid)
    return out


def _enemies_in_play(game) -> list[str]:
    out = []
    for iid, inst in game.state.cards_in_play.items():
        cd = game.state.get_card_data(inst.card_id)
        if cd is not None and cd.type.value == "enemy":
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
    if inst is not None:
        if instance_id in inv.threat_area:
            inv.threat_area.remove(instance_id)
        if to_encounter_discard:
            game.state.scenario.encounter_discard.append(inst.card_id)


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


def _enemy_attack(game, instance_id: str, investigator_id: str) -> None:
    inst = game.state.get_card_instance(instance_id)
    cd = game.state.get_card_data(inst.card_id) if inst else None
    if cd is None:
        return
    game.damage_engine.deal_damage(
        investigator_id, damage=cd.enemy_damage or 0,
        horror=cd.enemy_horror or 0, source=instance_id)


def _move_enemy_to_investigator_and_attack(game, instance_id: str, inv) -> None:
    """简化版"如同敌军阶段般移动并攻击"：就绪、移至该调查员处交战并攻击一次。"""
    inst = game.state.get_card_instance(instance_id)
    if inst is not None:
        inst.exhausted = False
    _engage_investigator(game, instance_id, inv)
    _enemy_attack(game, instance_id, inv.investigator_id)


def _pull_enemy_from_encounter(game, tag: str) -> str | None:
    """Search encounter deck then discard for an enemy with the tag."""
    s = game.state.scenario
    for pile in (s.encounter_deck, s.encounter_discard):
        for cid in list(pile):
            if _is_enemy_with_tag(game, cid, tag):
                pile.remove(cid)
                return cid
    return None


def _register_one_shot(game, event: GameEvent, handler) -> None:
    """Register an event handler that unregisters itself after firing once."""
    holder: list[Any] = []

    def _wrap(ctx):
        entry = holder[0]
        game.event_bus.unregister(entry)
        handler(ctx)

    holder.append(game.event_bus.register(event, _wrap, priority=TimingPriority.AFTER))


def _register_round_end_flag(game, flag: str) -> None:
    """Self-discard a 'next to the act/agenda deck' card at round end."""
    def _clear(_ctx):
        game.state.scenario.vars.pop(flag, None)
    _register_one_shot(game, GameEvent.ROUND_ENDS, _clear)


def _run_test_full(game, investigator_id: str, skill: Skill, difficulty: int,
                   on_success=None, on_failure=None) -> None:
    """Direct skill test with both callbacks (_run_skill_test 只暴露失败回调)。"""
    game.skill_test_engine.run_test(
        investigator_id=investigator_id,
        skill_type=skill,
        difficulty=difficulty,
        committed_card_ids=[],
        on_success=on_success or (lambda r: None),
        on_failure=on_failure or (lambda r: None),
    )


# ---------------------------------------------------------------------------
# 剧本子系统状态（均无引擎钩子，仅 vars 记录）
# ---------------------------------------------------------------------------

def _alarm(game, investigator_id: str) -> int:
    return int(game.state.scenario.vars.get("alarm_level", {}).get(investigator_id, 0) or 0)


def _raise_alarm(game, investigator_id: str, n: int = 1) -> None:
    levels = game.state.scenario.vars.setdefault("alarm_level", {})
    levels[investigator_id] = int(levels.get(investigator_id, 0) or 0) + n


def _is_enchanted_woods(game, loc) -> bool:
    cd = getattr(loc, "card_data", None)
    if cd is None:
        return False
    return (str(cd.id).startswith("enchanted_woods")
            or cd.name == "Enchanted Woods" or cd.name_cn == "魔幻森林")


def _location_traits(game, location_id: str) -> list[str]:
    loc = game.state.get_location(location_id)
    cd = getattr(loc, "card_data", None) if loc else None
    if cd is None:
        return []
    return list(getattr(cd, "traits", None) or []) + list(getattr(cd, "keywords", None) or [])


def _is_permanent(cd) -> bool:
    tags = list(getattr(cd, "keywords", None) or []) + list(getattr(cd, "traits", None) or [])
    return "permanent" in tags or "常驻" in tags


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

def resolve_treachery(controller, card_id: str, *, investigator_id: str,
                      choice: str | None = None) -> dict | None:
    """Resolve a Dream-Eaters treachery. Returns result dict, or None."""
    game = controller.game
    inv = game.state.get_investigator(investigator_id)
    if inv is None:
        return None
    log = controller.log
    run_test = controller._run_skill_test
    svars = game.state.scenario.vars

    # ---- Beyond the Gates of Sleep ----
    if card_id == "lost_in_the_woods":
        targets = [other for other in game.state.investigators.values()
                   if not other.is_defeated
                   and _is_enchanted_woods(game, game.state.get_location(other.location_id))]
        log(f"🌲 遭遇：森林迷途——涌动；{len(targets)} 位位于魔幻森林的调查员检定意志3"
            "（失败失去1行动并受1恐惧）")

        def _make_fail(target_id):
            def on_fail(_r):
                target = game.state.get_investigator(target_id)
                if target is None:
                    return
                if target.actions_remaining > 0:
                    target.actions_remaining -= 1
                game.damage_engine.deal_damage(target_id, horror=1)
            return on_fail
        for other in targets:
            run_test(other.investigator_id, skill=Skill.WILLPOWER, difficulty=3,
                     on_failure=_make_fail(other.investigator_id))
        return {"pending": False, "message": "surge", "surge": True}

    # ---- Waking Nightmare / Spiders / Agents of Atlach-Nacha ----
    if card_id == "outbreak":
        # 简化：蛛群滋生检定（独立滋生袋）无引擎支持——记录次数，未结算；
        # 位于蛛巢地点时 tablet 视为 skull 的替换同样未强制
        svars["infestation_test_count"] = int(svars.get("infestation_test_count", 0) or 0) + 1
        log("🕷️ 遭遇：爆发——进行一次蛛群滋生检定[机制未实现，仅记录]")
        return {"pending": False, "message": "outbreak"}

    if card_id == "will_of_the_spider_mother":
        spiders = [iid for iid in _enemies_with_tag(game, "spider")
                   if _enemy_location(game, iid) == inv.location_id]
        # 简化：同地点有蜘蛛时"不能投入卡牌"未强制（无投入拦截钩子）
        log("🕸️ 遭遇：蛛后的意志（意志3"
            + ("，同地点有蜘蛛——不能投入卡牌[未强制]" if spiders else "")
            + "，失败本轮不能攻击/调查）")

        def on_fail(_r):
            svars.setdefault("will_of_the_spider_mother", {})[investigator_id] = True

            def _clear(ctx):
                if ctx.investigator_id in (None, investigator_id):
                    svars.get("will_of_the_spider_mother", {}).pop(investigator_id, None)
            _register_one_shot(game, GameEvent.ROUND_ENDS, _clear)
            log("  → 本轮你不能攻击或调查（记入 vars，未强制）")
        run_test(investigator_id, skill=Skill.WILLPOWER, difficulty=3, on_failure=on_fail)
        return {"pending": False, "message": "will_of_the_spider_mother"}

    if card_id in _LAW_OF_YGIROTH:
        # 简化：数字版无法保密——直接加入手牌；持续限制记入 vars，未强制
        inv.hand.append(card_id)
        svars.setdefault("law_of_ygiroth", {})[investigator_id] = card_id
        log(f"📜 遭遇：伊吉若斯之理——加入手牌（{_LAW_OF_YGIROTH[card_id]}，限制未强制；"
            f"可用 activate_discard_law_of_ygiroth 花1行动弃1张满足偶数条件的玩家卡来弃掉）")
        return {"pending": False, "message": card_id}

    if card_id == "whispers_of_hypnos":
        rec = svars.setdefault("whispers_of_hypnos", {"skills": []})
        chosen = list(rec.get("skills", []))
        pool = [sk for sk in ("willpower", "intellect", "combat", "agility") if sk not in chosen]
        if choice is None:
            svars["pending_choice"] = {
                "card_id": card_id,
                "investigator_id": investigator_id,
                "prompt": "修普诺斯的低语：选择一项技能（本轮所有调查员该技能-2）",
                "options": [{"id": sk, "label": sk} for sk in pool],
            }
            return {"pending": True, "message": "pending_choice"}
        if choice not in pool:
            choice = pool[0] if pool else "willpower"
        skill = Skill(choice)
        rec["skills"].append(choice)

        def _penalty(ctx):
            if ctx.skill_type == skill and choice in svars.get("whispers_of_hypnos", {}).get("skills", []):
                ctx.modify_amount(-2, "whispers_of_hypnos")

        pen_entry = game.event_bus.register(
            GameEvent.SKILL_VALUE_DETERMINED, _penalty, priority=TimingPriority.WHEN)

        def _clear(_ctx):
            game.event_bus.unregister(pen_entry)
            rec = svars.get("whispers_of_hypnos")
            if rec and choice in rec.get("skills", []):
                rec["skills"].remove(choice)
        _register_one_shot(game, GameEvent.ROUND_ENDS, _clear)
        log(f"😴 遭遇：修普诺斯的低语——本轮所有调查员 {choice} -2（轮末弃掉）")
        return {"pending": False, "message": "whispers_of_hypnos"}

    # ---- Dreamer's Curse ----
    if card_id == "dreamers_curse":
        # 简化：投入图标计数修正（智力/战斗/敏捷算匹配、意志/百搭算2）未强制
        # （图标计数在会话层，无钩子）
        log("🌀 遭遇：入梦者的诅咒（意志5，失败按差额受伤，至多3）")
        run_test(investigator_id, skill=Skill.WILLPOWER, difficulty=5,
                 on_failure=lambda r: game.damage_engine.deal_damage(
                     investigator_id, damage=min(3, _margin_fail(r))))
        return {"pending": False, "message": "dreamers_curse"}

    if card_id == "somniphobia":
        log("😱 遭遇：睡眠恐惧症（意志5，失败按差额受恐惧，至多3）")
        run_test(investigator_id, skill=Skill.WILLPOWER, difficulty=5,
                 on_failure=lambda r: game.damage_engine.deal_damage(
                     investigator_id, horror=min(3, _margin_fail(r))))
        return {"pending": False, "message": "somniphobia"}

    if card_id == "deeper_slumber":
        _place_in_threat(game, inv, "deeper_slumber")
        # 简化：手牌上限-3 未强制（phase_upkeep._check_hand_size 为硬编码，引擎缺口）
        svars.setdefault("deeper_slumber", {})[investigator_id] = True
        log("💤 遭遇：沉眠——放入威胁区（手牌上限-3[未强制]；"
            "可用 activate_discard_deeper_slumber 花2行动弃掉）")
        return {"pending": False, "message": "deeper_slumber"}

    # ---- Dreamlands ----
    if card_id == "dreamlands_eclipse":
        # 简化：调查开始时 1恐惧 或 地点+2隐蔽 的强制效果未强制（无调查开始钩子）；
        # 本轮结束自动弃掉
        svars["dreamlands_eclipse"] = True
        _register_round_end_flag(game, "dreamlands_eclipse")
        log("🌒 遭遇：幻梦境月食——放在密谋旁（调查开始需受1恐惧或+2隐蔽[未强制]，轮末弃掉）")
        return {"pending": False, "message": "dreamlands_eclipse"}

    if card_id == "prismatic_phenomenon":
        iid = _place_in_threat(game, inv, "prismatic_phenomenon")
        # 简化：每轮首次抽牌/资源/打出行动+1行动 未强制（无费用修正钩子）
        svars.setdefault("prismatic_phenomenon", {})[investigator_id] = True

        holder: list[Any] = []

        def _on_clue(ctx):
            if ctx.investigator_id != investigator_id:
                return
            if _threat_copy(game, inv, "prismatic_phenomenon") is None:
                game.event_bus.unregister(holder[0])
                return
            # 简化：调查成功不发现线索——撤回刚发现的1个线索并弃掉本卡
            if inv.clues > 0:
                inv.clues -= 1
                loc = game.state.get_location(ctx.location_id or inv.location_id)
                if loc is not None:
                    loc.clues += 1
            game.event_bus.unregister(holder[0])
            _remove_from_threat(game, inv, _threat_copy(game, inv, "prismatic_phenomenon"))
            svars.get("prismatic_phenomenon", {}).pop(investigator_id, None)
            log("🌈 棱镜光华：调查成功——改为弃掉棱镜光华（撤回1线索）")

        holder.append(game.event_bus.register(GameEvent.CLUE_DISCOVERED, _on_clue,
                                              priority=TimingPriority.AFTER))
        log("🌈 遭遇：棱镜光华——放入威胁区（每轮首次抽牌/资源/打出+1行动[未强制]；"
            "调查成功时改为弃掉本卡）")
        return {"pending": False, "message": "prismatic_phenomenon"}

    # ---- Merging Realities ----
    if card_id == "night_terrors":
        _place_in_threat(game, inv, "night_terrors")
        svars.setdefault("night_terrors", {})[investigator_id] = True

        holder: list[Any] = []

        def _on_fail(ctx):
            if ctx.investigator_id != investigator_id:
                return
            if _threat_copy(game, inv, "night_terrors") is None:
                game.event_bus.unregister(holder[0])
                return
            revealed = [inv.deck.pop(0) for _ in range(min(3, len(inv.deck)))]
            weaknesses = [c for c in revealed if is_weakness_card(game.state.get_card_data(c))]
            removed = [c for c in revealed if c not in weaknesses]
            for c in weaknesses:
                inv.hand.append(c)
            if removed:
                svars.setdefault("removed_from_game", []).extend(removed)
            log(f"😨 黑夜恐怖：检定失败后翻开牌堆顶{len(revealed)}张——"
                f"抽到弱点【{_log_names(game, weaknesses)}】" if weaknesses else
                f"😨 黑夜恐怖：检定失败后翻开牌堆顶{len(revealed)}张——无弱点，移出游戏")

        holder.append(game.event_bus.register(GameEvent.SKILL_TEST_FAILED, _on_fail,
                                              priority=TimingPriority.AFTER))
        log("😨 遭遇：黑夜恐怖——放入威胁区（检定失败后翻牌堆顶3张抽弱点；"
            "可用 activate_discard_night_terrors 花1行动意志4弃掉）")
        return {"pending": False, "message": "night_terrors"}

    if card_id == "glimpse_of_the_underworld":
        _place_in_threat(game, inv, "glimpse_of_the_underworld")
        # 简化：受伤害/恐惧时额外+1 未强制（无伤害修正钩子，引擎缺口）
        svars.setdefault("glimpse_of_the_underworld", {})[investigator_id] = True
        log("🕳️ 遭遇：窥看地下世界——放入威胁区（受伤害/恐惧额外+1[未强制]；"
            "可用 activate_discard_glimpse [快速]弃掉并受1伤1恐）")
        return {"pending": False, "message": "glimpse_of_the_underworld"}

    if card_id == "threads_of_reality":
        candidates = []
        for iid in inv.play_area:
            inst = game.state.get_card_instance(iid)
            cd = game.state.get_card_data(inst.card_id) if inst else None
            if cd is None or cd.type.value != "asset":
                continue
            if _is_permanent(cd) or is_weakness_card(cd):
                continue
            candidates.append((cd.cost or 0, iid))
        if not candidates:
            log("🧵 遭遇：现实之线——无可叠加支援，涌动")
            return {"pending": False, "message": "surge", "surge": True}
        candidates.sort(key=lambda t: t[0])
        asset_iid = candidates[-1][1]
        inst_id = game.state.next_instance_id()
        game.state.cards_in_play[inst_id] = CardInstance(
            instance_id=inst_id, card_id="threads_of_reality",
            owner_id="scenario", controller_id="scenario", attached_to=asset_iid)
        # 简化：被叠加支援文本框视为空白 未强制（无文本屏蔽钩子）
        svars.setdefault("threads_of_reality", {})[investigator_id] = {
            "instance_id": inst_id, "asset": asset_iid}
        log(f"🧵 遭遇：现实之线——叠加到【{game.state.card_name(game.state.get_card_instance(asset_iid).card_id)}】"
            "（其文本视为空白[未强制]；可用 activate_discard_threads_of_reality 花1行动弃1支援来弃掉）")
        return {"pending": False, "message": "threads_of_reality"}

    # ---- Spiders ----
    if card_id == "sickening_webs":
        controller.attach_card_to_location("sickening_webs", inv.location_id)
        # 简化：该地点蜘蛛获得反击/警觉、调查员不能离开 均未强制（无对应钩子）
        svars.setdefault("sickening_webs", {})[inv.location_id] = True
        log("🕸️ 遭遇：恶心蛛网——叠加到所在地点（该地点蜘蛛反击+警觉、不能离开[均未强制]；"
            "可用 activate_sickening_webs 花1行动战斗/敏捷3弃掉）")
        return {"pending": False, "message": "sickening_webs"}

    # ---- Corsairs ----
    if card_id == "hunted_by_corsairs":
        # 简化：叠加到当前场景——引擎无场景附属框架与场景推进事件，
        # "场景推进时每人受2伤害"未强制；记入 vars
        svars["hunted_by_corsairs"] = True
        log("🏴‍☠️ 遭遇：海盗追猎——叠加到当前场景（场景推进时每人受2伤害[未强制]；"
            "可用 activate_hunted_by_corsairs 花1行动智力/敏捷4弃掉）")
        return {"pending": False, "message": "hunted_by_corsairs"}

    # ---- Zoogs ----
    if card_id == "zoog_burrow":
        log("🐀 遭遇：祖格鼠的地穴（敏捷3，失败按差额给最近蜂拥祖格鼠加蜂拥卡）")

        def on_fail(r):
            m = _margin_fail(r)
            if m <= 0:
                return
            zoogs = [iid for iid in _enemies_with_tag(game, "zoog")
                     if any(t.startswith("swarming") for t in _tags_of(game, iid))]
            if zoogs:
                # 简化：蜂拥卡记入 uses["swarm"]（无蜂拥框架）；"最近"取第一个
                inst = game.state.get_card_instance(zoogs[0])
                inst.uses["swarm"] = inst.uses.get("swarm", 0) + m
                log(f"  → 【{game.state.card_name(inst.card_id)}】增加{m}张蜂拥卡")
                return
            pulled = _pull_enemy_from_encounter(game, "zoog")
            if pulled:
                controller._spawn_enemy_from_encounter(pulled, investigator_id)
                random.shuffle(game.state.scenario.encounter_deck)
                log(f"  → 场上无蜂拥祖格鼠，抽到【{game.state.card_name(pulled)}】")
        run_test(investigator_id, skill=Skill.AGILITY, difficulty=3, on_failure=on_fail)
        return {"pending": False, "message": "zoog_burrow"}

    # ---- The Search for Kadath ----
    if card_id == "song_of_the_magah_bird":
        controller.attach_card_to_location("song_of_the_magah_bird", inv.location_id)
        attached_loc = inv.location_id

        holder: list[Any] = []

        def _on_move(ctx):
            if controller.location_attachment_instance(attached_loc, "song_of_the_magah_bird") is None:
                game.event_bus.unregister(holder[0])
                return
            moving = game.state.get_investigator(ctx.investigator_id)
            if moving is None or moving.location_id != attached_loc:
                return
            if ctx.location_id == attached_loc:
                return
            game.event_bus.unregister(holder[0])
            game.damage_engine.deal_damage(ctx.investigator_id, horror=1)
            game.state.scenario.doom_on_agenda += 1
            controller._check_agenda_threshold()
            iid = controller.location_attachment_instance(attached_loc, "song_of_the_magah_bird")
            controller.detach_card_from_location(iid)
            log(f"🐦 麦格鸟之歌：【{ctx.investigator_id}】离开被叠加地点——受1恐惧，密谋+1毁灭，弃掉本卡")

        holder.append(game.event_bus.register(GameEvent.MOVE_ACTION_INITIATED, _on_move,
                                              priority=TimingPriority.AFTER))
        log("🐦 遭遇：麦格鸟之歌——叠加到所在地点（离开者受1恐惧+密谋+1毁灭；"
            "可用 activate_song_of_the_magah_bird 花1行动意志/战斗4弃掉）")
        return {"pending": False, "message": "song_of_the_magah_bird"}

    if card_id == "wondrous_lands":
        loc = game.state.get_location(inv.location_id)
        if loc is None or loc.clues <= 0:
            log("🏞️ 遭遇：奇妙平原——所在地点无线索，弃掉并涌动")
            return {"pending": False, "message": "surge", "surge": True}
        controller.attach_card_to_location("wondrous_lands", inv.location_id)
        attached_loc = inv.location_id
        # 简化：地点-2隐蔽 未强制（location_shroud_bonus 硬编码白名单，引擎缺口）

        holder: list[Any] = []

        def _on_clue(ctx):
            if ctx.location_id != attached_loc:
                return
            if controller.location_attachment_instance(attached_loc, "wondrous_lands") is None:
                game.event_bus.unregister(holder[0])
                return
            game.event_bus.unregister(holder[0])
            game.damage_engine.deal_damage(ctx.investigator_id or investigator_id, horror=1)
            game.state.scenario.doom_on_agenda += 1
            controller._check_agenda_threshold()
            iid = controller.location_attachment_instance(attached_loc, "wondrous_lands")
            controller.detach_card_from_location(iid)
            log("🏞️ 奇妙平原：被叠加地点调查成功——受1恐惧，密谋+1毁灭，弃掉本卡")

        holder.append(game.event_bus.register(GameEvent.CLUE_DISCOVERED, _on_clue,
                                              priority=TimingPriority.AFTER))
        log("🏞️ 遭遇：奇妙平原——叠加到所在地点（-2隐蔽[未强制]；该地点调查成功后受1恐惧+密谋+1毁灭）")
        return {"pending": False, "message": "wondrous_lands"}

    # ---- A Thousand Shapes of Horror ----
    if card_id == "endless_descent":
        # 简化：深渊地点线（vars["pitch_locations"]，顶端→底端排序）存在时才执行
        # 移动/翻面/轮转；未揭示位置混洗按官方执行
        pitch = list(svars.get("pitch_locations") or [])
        pitch = [p for p in pitch if p in game.state.locations]
        if len(pitch) >= 2:
            top, below = pitch[0], pitch[1]
            top_loc = game.state.get_location(top)
            below_loc = game.state.get_location(below)
            for other in game.state.investigators.values():
                if other.location_id == top:
                    other.location_id = below
            for eid in list(top_loc.enemies):
                top_loc.enemies.remove(eid)
                below_loc.enemies.append(eid)
            top_loc.revealed = False
            top_loc.clues = 0
            top_loc.doom = 0
            for iid in list(top_loc.attachments):
                controller.detach_card_from_location(iid)
            pitch.append(pitch.pop(0))
            # 混洗未揭示地点的位置（保持已揭示者位置不变）
            unrevealed = [p for p in pitch if not game.state.get_location(p).revealed]
            shuffled = list(unrevealed)
            random.shuffle(shuffled)
            it = iter(shuffled)
            pitch = [next(it) if not game.state.get_location(p).revealed else p for p in pitch]
            svars["pitch_locations"] = pitch
            log(f"🕳️ 遭遇：无尽深入——顶端地点【{top}】翻回未揭示并移到底端，所有人/敌人下移")
        else:
            log("🕳️ 遭遇：无尽深入——（无深渊地点线，仅加入胜利展示区）")
        game.state.scenario.victory_display.append("endless_descent")
        return {"pending": False, "message": "endless_descent"}

    if card_id == "indescribable_apparition":
        _place_in_threat(game, inv, "indescribable_apparition")
        # 简化：不可名状者在你地点时全技能-1 未强制（无条件技能修正钩子）
        svars.setdefault("indescribable_apparition", {})[investigator_id] = True
        log("👤 遭遇：难以描述的鬼魅——放入威胁区（不可名状者同地点时全技能-1[未强制]；"
            "可用 activate_discard_indescribable_apparition 花2行动弃掉）")
        return {"pending": False, "message": "indescribable_apparition"}

    if card_id == "glowing_eyes":
        _place_in_threat(game, inv, "glowing_eyes")

        def _on_round_end(_ctx):
            n = min(3, len(inv.threat_area))
            if n > 0:
                game.damage_engine.deal_damage(investigator_id, horror=n)
            iid = _threat_copy(game, inv, "glowing_eyes")
            if iid is not None:
                _remove_from_threat(game, inv, iid)
            log(f"👁️ 发光的眼睛：本轮结束——按威胁区卡牌数受{n}恐惧，弃掉发光的眼睛")

        _register_one_shot(game, GameEvent.ROUND_ENDS, _on_round_end)
        log("👁️ 遭遇：发光的眼睛——放入威胁区（轮末按威胁区卡牌数受恐惧，至多3，然后弃掉）")
        return {"pending": False, "message": "glowing_eyes"}

    if card_id == "deceptive_memories":
        _place_in_threat(game, inv, "deceptive_memories")
        # 简化：另一张卡进入你威胁区时弃1手牌 未强制（无威胁区进入事件，引擎缺口）
        svars.setdefault("deceptive_memories", {})[investigator_id] = True
        log("🧠 遭遇：欺骗性记忆——放入威胁区（另有卡进入威胁区时弃1手牌[未强制]；"
            "可用 activate_deceptive_memories 花1行动意志3弃掉）")
        return {"pending": False, "message": "deceptive_memories"}

    if card_id == "secrets_in_the_attic":
        log("🗝️ 遭遇：阁楼的秘密（意志3，失败受1恐惧并放到密谋旁）")

        def on_fail(_r):
            game.damage_engine.deal_damage(investigator_id, horror=1)
            # 简化：地点上的[快速]能力不能触发 未强制（无能力拦截钩子）
            svars["secrets_in_the_attic"] = int(svars.get("secrets_in_the_attic", 0) or 0) + 1

            def _on_round_end(_ctx2):
                if svars.get("secrets_in_the_attic", 0) > 0:
                    svars["secrets_in_the_attic"] -= 1
                    log("🗝️ 阁楼的秘密：本轮结束——弃掉1份阁楼的秘密")
            _register_one_shot(game, GameEvent.ROUND_ENDS, _on_round_end)
        run_test(investigator_id, skill=Skill.WILLPOWER, difficulty=3, on_failure=on_fail)
        return {"pending": False, "message": "secrets_in_the_attic"}

    # ---- Dark Side of the Moon ----
    if card_id == "close_watch":
        log("👮 遭遇：严密监视（敏捷4，失败：弃最高费支援 或 警戒等级+1）")

        def on_fail(_r):
            # 简化：自动选择警戒等级+1（官方二选一，通常代价更小）
            _raise_alarm(game, investigator_id, 1)
            log(f"  → 警戒等级+1（现为{_alarm(game, investigator_id)}）")
        run_test(investigator_id, skill=Skill.AGILITY, difficulty=4, on_failure=on_fail)
        return {"pending": False, "message": "close_watch"}

    if card_id == "forced_into_hiding":
        x = _alarm(game, investigator_id)
        log(f"🫣 遭遇：被迫藏身（意志{x}，失败失去1行动；差3+失去2；差5+失去3）")

        def on_fail(r):
            m = _margin_fail(r)
            lose = 3 if m >= 5 else 2 if m >= 3 else 1
            lost = min(lose, inv.actions_remaining)
            inv.actions_remaining -= lost
            log(f"  → 失去{lost}个行动")
        run_test(investigator_id, skill=Skill.WILLPOWER, difficulty=x, on_failure=on_fail)
        return {"pending": False, "message": "forced_into_hiding"}

    if card_id == "lunar_patrol":
        controller.attach_card_to_location("lunar_patrol", inv.location_id)
        attached_loc = inv.location_id

        holder: list[Any] = []

        def _on_move(ctx):
            if controller.location_attachment_instance(attached_loc, "lunar_patrol") is None:
                game.event_bus.unregister(holder[0])
                return
            moving = game.state.get_investigator(ctx.investigator_id)
            if moving is None or moving.location_id != attached_loc:
                return
            if ctx.location_id == attached_loc:
                return
            _raise_alarm(game, ctx.investigator_id, 1)
            log(f"🌙 月球巡逻：【{ctx.investigator_id}】离开被叠加地点，警戒等级+1")

        holder.append(game.event_bus.register(GameEvent.MOVE_ACTION_INITIATED, _on_move,
                                              priority=TimingPriority.AFTER))
        log("🌙 遭遇：月球巡逻——叠加到所在地点（离开者警戒等级+1；"
            "可用 activate_lunar_patrol 花1行动敏捷3弃掉）")
        return {"pending": False, "message": "lunar_patrol"}

    if card_id in ("false_awakening_a", "false_awakening_b"):
        # 官方：开局即放在密谋旁且有1毁灭，不会从遭遇牌堆抽到；
        # 若被结算（防护性处理）则按入场处理
        rec = svars.setdefault("false_awakening", {})
        rec[card_id] = {"doom": 1}
        log("⏰ 遭遇：梦中甦醒——放在密谋旁，上有1毁灭"
            "（可用 activate_false_awakening 花1行动任意技能(2+调查员数)移出游戏）")
        return {"pending": False, "message": card_id}

    # ---- Point of No Return ----
    if card_id == "taste_of_lifeblood":
        log("🩸 遭遇：鲜血的滋味（意志3，失败按差额：放1线索到地点/最近敌人 或 受1伤害）")

        def on_fail(r):
            for _ in range(_margin_fail(r)):
                # 简化：自动优先把线索放到所在地点（官方三选一），无线索则受1伤害
                if inv.clues > 0:
                    inv.clues -= 1
                    loc = game.state.get_location(inv.location_id)
                    if loc is not None:
                        loc.clues += 1
                else:
                    game.damage_engine.deal_damage(investigator_id, damage=1)
        run_test(investigator_id, skill=Skill.WILLPOWER, difficulty=3, on_failure=on_fail)
        return {"pending": False, "message": "taste_of_lifeblood"}

    if card_id == "lit_by_death_fire":
        for other in game.state.investigators.values():
            if other.is_defeated:
                continue
            other.resources = max(0, other.resources - 1)
            traits = _location_traits(game, other.location_id)
            if "vale" in traits or "depths" in traits or "溪谷" in traits or "深渊" in traits:
                if other.hand:
                    cid = other.hand.pop(0)  # 简化：自动弃第一张（官方由你选择）
                    other.discard.append(cid)
                    log(f"🔥 夺命猛火：【{other.investigator_id}】弃掉【{game.state.card_name(cid)}】")
            if "depths" in traits or "深渊" in traits:
                if other.actions_remaining > 0:
                    other.actions_remaining -= 1
        log("🔥 遭遇：夺命猛火——每人失去1资源；溪谷/深渊地点者弃1手牌；深渊地点者失去1行动")
        return {"pending": False, "message": "lit_by_death_fire"}

    if card_id == "unexpected_ambush":
        enemies = _enemies_in_play(game)
        if not enemies:
            game.damage_engine.deal_damage(investigator_id, damage=1, horror=1)
            log("🗡️ 遭遇：意外伏击——场上无敌人，受1伤1恐")
            return {"pending": False, "message": "unexpected_ambush"}
        # 简化：自动选智力/敏捷中较高者检定（官方由你选择检定技能）
        skill = Skill.INTELLECT if inv.get_skill(Skill.INTELLECT) >= inv.get_skill(Skill.AGILITY) \
            else Skill.AGILITY
        log(f"🗡️ 遭遇：意外伏击（{'智力' if skill == Skill.INTELLECT else '敏捷'}4，"
            "失败最近敌人就绪交战；差3+立即攻击）")

        def on_fail(r):
            target = controller._nearest_enemy_with(inv, None) or enemies[0]
            inst = game.state.get_card_instance(target)
            if inst is not None:
                inst.exhausted = False
            # 简化：直接移至调查员地点交战（官方逐地点移动，结果相同）
            _engage_investigator(game, target, inv)
            log(f"  → 【{game.state.card_name(game.state.get_card_instance(target).card_id)}】就绪并与你交战")
            if _margin_fail(r) >= 3:
                _enemy_attack(game, target, investigator_id)
                log("  → 失败差3+，立即攻击")
        run_test(investigator_id, skill=skill, difficulty=4, on_failure=on_fail)
        return {"pending": False, "message": "unexpected_ambush"}

    # ---- Terror of the Vale ----
    if card_id == "dhole_tunnel":
        dhole = [iid for iid, inst in game.state.cards_in_play.items()
                 if inst.card_id == "slithering_dhole"]
        if dhole:
            # 简化："如同敌军阶段般移动并攻击"——移至抽卡调查员处交战并攻击一次
            _move_enemy_to_investigator_and_attack(game, dhole[0], inv)
            log("🪱 遭遇：巨噬蠕虫隧道——滑行巨噬蠕虫移动并攻击你（如同敌军阶段）")
            return {"pending": False, "message": "dhole_tunnel"}
        tunnel_locs = [loc_id for loc_id in game.state.locations
                       if controller.location_attachment_instance(loc_id, "dhole_tunnel")]
        candidates = []
        for loc_id in game.state.locations:
            if not tunnel_locs:
                candidates.append(loc_id)
                continue
            dists = [controller._bfs_distance(loc_id, t) for t in tunnel_locs]
            if min(dists) >= 2:
                candidates.append(loc_id)
        # 优先叠加到当前地点（若合法），否则第一个合法地点；均不可则当前地点
        target_loc = inv.location_id if inv.location_id in candidates else \
            (candidates[0] if candidates else inv.location_id)
        controller.attach_card_to_location("dhole_tunnel", target_loc)
        msg = f"🪱 遭遇：巨噬蠕虫隧道——叠加到【{target_loc}】"
        if "slithering_dhole" in game.state.scenario.victory_display:
            game.state.scenario.victory_display.remove("slithering_dhole")
            iid = game.state.next_instance_id()
            game.state.cards_in_play[iid] = CardInstance(
                instance_id=iid, card_id="slithering_dhole",
                owner_id="scenario", controller_id="scenario", exhausted=True)
            loc = game.state.get_location(target_loc)
            if loc is not None:
                loc.enemies.append(iid)
            msg += "；滑行巨噬蠕虫从胜利展示区在该地点耗尽生成"
        log(msg)
        return {"pending": False, "message": "dhole_tunnel"}

    # ---- Descent into the Pitch ----
    if card_id == "shadow_of_atlach_nacha":
        bonus = int(svars.get("scenario_reference_damage", 0) or 0)
        difficulty = 2 + bonus
        log(f"🕷️ 遭遇：阿特拉克·纳克亚之影（意志{difficulty}，失败受1伤1恐）")
        run_test(investigator_id, skill=Skill.WILLPOWER, difficulty=difficulty,
                 on_failure=lambda r: game.damage_engine.deal_damage(
                     investigator_id, damage=1, horror=1))
        return {"pending": False, "message": "shadow_of_atlach_nacha"}

    # ---- Where the Gods Dwell ----
    if card_id in _WHISPERING_CHAOS_TOWER:
        # 简化：数字版无法保密——直接加入手牌；方塔能力（剧本机制）未实现，
        # 记入 vars 供剧本层使用
        inv.hand.append(card_id)
        svars.setdefault("whispering_chaos", {})[investigator_id] = card_id
        log(f"🌀 遭遇：混沌低语——加入手牌（{_WHISPERING_CHAOS_TOWER[card_id]}"
            f"能力[未实现]）")
        return {"pending": False, "message": card_id}

    if card_id == "myriad_forms":
        attacked = False
        in_hand = [c for c in list(inv.hand) if str(c).startswith("nyarlathotep")]
        for cid in in_hand:
            inv.hand.remove(cid)
            cd = game.state.get_card_data(cid)
            game.damage_engine.deal_damage(
                investigator_id,
                damage=(cd.enemy_damage or 0) if cd else 1,
                horror=(cd.enemy_horror or 0) if cd else 0)
            game.state.scenario.encounter_deck.append(cid)
            attacked = True
            log(f"🎭 化身万千：手中的【{game.state.card_name(cid)}】攻击你后洗入遭遇牌堆")
        if in_hand:
            random.shuffle(game.state.scenario.encounter_deck)
        in_play = [iid for iid, inst in game.state.cards_in_play.items()
                   if str(inst.card_id).startswith("nyarlathotep")]
        if in_play:
            # 简化："如同敌军阶段般移动并攻击"——交战并攻击一次
            _move_enemy_to_investigator_and_attack(game, in_play[0], inv)
            attacked = True
            log("🎭 化身万千：场上的奈亚拉托提普移动并攻击你（如同敌军阶段）")
        if not attacked:
            log("🎭 遭遇：化身万千——无奈亚拉托提普攻击，涌动")
            return {"pending": False, "message": "surge", "surge": True}
        return {"pending": False, "message": "myriad_forms"}

    if card_id in _RESTLESS_JOURNEY_SKILL:
        # 简化：数字版无法保密——直接加入手牌；每轮投入≤1张 未强制
        inv.hand.append(card_id)
        svars.setdefault("restless_journey", {})[investigator_id] = card_id
        log("🚶 遭遇：无眠之旅——加入手牌（每轮投入检定≤1张[未强制]；"
            "可用 activate_restless_journey [快速]弃掉并检定，失败密谋+1毁灭）")
        return {"pending": False, "message": card_id}

    if card_id == "abandoned_by_the_gods":
        log("⚡ 遭遇：众神所弃（意志3，失败按差额选择0-4的数字，弃对应费用的事件/支援）")

        def on_fail(r):
            m = _margin_fail(r)
            if m <= 0:
                return
            # 简化：自动选择全场手牌中匹配最少的数字（官方由你选择）
            counts = {n: 0 for n in range(5)}
            for other in game.state.investigators.values():
                for cid in other.hand:
                    cd = game.state.get_card_data(cid)
                    if cd is not None and cd.type.value in ("asset", "event"):
                        cost = cd.cost or 0
                        if cost in counts:
                            counts[cost] += 1
            chosen = sorted(counts, key=lambda n: (counts[n], n))[:m]
            for other in game.state.investigators.values():
                for cid in list(other.hand):
                    cd = game.state.get_card_data(cid)
                    if cd is not None and cd.type.value in ("asset", "event") \
                            and (cd.cost or 0) in chosen:
                        other.hand.remove(cid)
                        other.discard.append(cid)
                        log(f"  → 【{other.investigator_id}】弃掉【{game.state.card_name(cid)}】")
            log(f"  → 选择数字 {chosen}")
        run_test(investigator_id, skill=Skill.WILLPOWER, difficulty=3, on_failure=on_fail)
        return {"pending": False, "message": "abandoned_by_the_gods"}

    # ---- Weaver of the Cosmos ----
    if card_id == "the_spinner_in_darkness":
        ancient_ones = _enemies_with_tag(game, "ancient one") + _enemies_with_tag(game, "ancient_one")
        if not ancient_ones:
            # 卡面无 surge 条款：无可叠加目标时直接弃掉（无效果）
            log("🕸️ 遭遇：黑暗中的织网者——场上无古神敌人，直接弃掉")
            return {"pending": False, "message": "the_spinner_in_darkness"}
        target = ancient_ones[0]  # 简化："最近"取第一个（无距离排序）
        inst_id = game.state.next_instance_id()
        game.state.cards_in_play[inst_id] = CardInstance(
            instance_id=inst_id, card_id="the_spinner_in_darkness",
            owner_id="scenario", controller_id="scenario", attached_to=target)
        # 简化：+1伤害/+1恐惧 未强制（攻击数值在伤害引擎内读取卡面，无修正钩子）
        svars.setdefault("spinner_in_darkness", {})[target] = inst_id
        log(f"🕸️ 遭遇：黑暗中的织网者——叠加到【{game.state.card_name(game.state.get_card_instance(target).card_id)}】"
            "（+1伤/+1恐[未强制]；可用 activate_spinner_in_darkness 花1行动任意技能5弃掉）")
        return {"pending": False, "message": "the_spinner_in_darkness"}

    if card_id == "caught_in_a_web":
        _place_in_threat(game, inv, "caught_in_a_web")
        # 简化：-1敏捷、每轮最多1次移动 未强制（无对应钩子）
        svars.setdefault("caught_in_a_web", {})[investigator_id] = True
        log("🕸️ 遭遇：陷入网中——放入威胁区（-1敏捷、每轮最多移动1次[均未强制]；"
            "可用 activate_caught_in_a_web 花1行动战斗3弃掉）")
        return {"pending": False, "message": "caught_in_a_web"}

    if card_id == "endless_weaving":
        spiders = _enemies_with_tag(game, "spider")
        if spiders:
            target = spiders[0]  # 简化："选择一个蜘蛛敌人"自动取第一个
            engaged_with = None
            for other in game.state.investigators.values():
                if target in other.threat_area:
                    engaged_with = other
                    break
            inst = game.state.get_card_instance(target)
            if engaged_with is not None:
                # 简化：蜂拥/宿主卡的协同攻击未实现（无蜂拥框架），仅本体攻击一次
                _enemy_attack(game, target, engaged_with.investigator_id)
                log(f"🕸️ 遭遇：无休织作——【{game.state.card_name(inst.card_id)}】立即攻击【{engaged_with.investigator_id}】")
            else:
                loc_id = _enemy_location(game, target)
                loc = game.state.get_location(loc_id) if loc_id else None
                if loc is not None:
                    loc.doom += 1
                controller._check_agenda_threshold()
                log(f"🕸️ 遭遇：无休织作——【{game.state.card_name(inst.card_id)}】所在地点+1毁灭")
            return {"pending": False, "message": "endless_weaving"}
        pulled = _pull_enemy_from_encounter(game, "spider")
        if pulled:
            controller._spawn_enemy_from_encounter(pulled, investigator_id)
            log(f"🕸️ 遭遇：无休织作——抽到【{game.state.card_name(pulled)}】")
        else:
            log("🕸️ 遭遇：无休织作——遭遇牌堆/弃牌堆中无蜘蛛敌人")
        random.shuffle(game.state.scenario.encounter_deck)
        return {"pending": False, "message": "endless_weaving"}

    return None


# ---------------------------------------------------------------------------
# 公开激活方法（Hidden/持续卡的 [行动]/[快速] 能力；供 session 层/测试调用）
# ---------------------------------------------------------------------------

def _law_discard_predicate(card_id: str, cd) -> bool:
    """伊吉若斯之理 [行动] 弃牌条件：满足对应"偶数"的玩家卡。"""
    if cd is None or cd.type.value not in ("asset", "event", "skill"):
        return False
    if card_id == "law_of_ygiroth_a":
        return (cd.cost or 0) % 2 == 0
    if card_id == "law_of_ygiroth_b":
        return sum((cd.skill_icons or {}).values()) % 2 == 0
    return len((cd.name or "").split()) % 2 == 0


def activate_discard_law_of_ygiroth(controller, investigator_id: str) -> bool:
    """[行动]：弃掉手牌中1张满足偶数条件的玩家卡，弃掉伊吉若斯之理。

    简化：自动选择手牌中第一张满足条件的卡（官方由你选择）。
    """
    game = controller.game
    inv = game.state.get_investigator(investigator_id)
    if inv is None or inv.actions_remaining < 1:
        return False
    card_id = game.state.scenario.vars.get("law_of_ygiroth", {}).get(investigator_id)
    if card_id is None or card_id not in inv.hand:
        return False
    target = None
    for cid in inv.hand:
        if cid == card_id:
            continue
        if _law_discard_predicate(card_id, game.state.get_card_data(cid)):
            target = cid
            break
    if target is None:
        return False
    inv.actions_remaining -= 1
    inv.hand.remove(target)
    inv.discard.append(target)
    inv.hand.remove(card_id)
    inv.discard.append(card_id)
    game.state.scenario.vars.get("law_of_ygiroth", {}).pop(investigator_id, None)
    controller.log(f"📜 花1行动：弃掉【{game.state.card_name(target)}】与【{game.state.card_name(card_id)}】")
    return True


def activate_discard_deeper_slumber(controller, investigator_id: str) -> bool:
    """[行动][行动]：弃掉威胁区中的沉眠。"""
    game = controller.game
    inv = game.state.get_investigator(investigator_id)
    if inv is None or inv.actions_remaining < 2:
        return False
    iid = _threat_copy(game, inv, "deeper_slumber")
    if iid is None:
        return False
    inv.actions_remaining -= 2
    _remove_from_threat(game, inv, iid)
    game.state.scenario.vars.get("deeper_slumber", {}).pop(investigator_id, None)
    controller.log("💤 花2行动弃掉【沉眠】")
    return True


def activate_discard_night_terrors(controller, investigator_id: str) -> bool:
    """[行动]：检定意志4；无论成败，检定结束后弃掉黑夜恐怖。"""
    game = controller.game
    inv = game.state.get_investigator(investigator_id)
    if inv is None or inv.actions_remaining < 1:
        return False
    iid = _threat_copy(game, inv, "night_terrors")
    if iid is None:
        return False
    inv.actions_remaining -= 1

    def _done(_r):
        cur = _threat_copy(game, inv, "night_terrors")
        if cur is not None:
            _remove_from_threat(game, inv, cur)
        game.state.scenario.vars.get("night_terrors", {}).pop(investigator_id, None)
        controller.log("😨 检定结束，弃掉【黑夜恐怖】")

    _run_test_full(game, investigator_id, Skill.WILLPOWER, 4,
                   on_success=_done, on_failure=_done)
    return True


def activate_discard_glimpse(controller, investigator_id: str) -> bool:
    """[快速]：弃掉窥看地下世界，然后受1伤害和1恐惧。"""
    game = controller.game
    inv = game.state.get_investigator(investigator_id)
    if inv is None:
        return False
    iid = _threat_copy(game, inv, "glimpse_of_the_underworld")
    if iid is None:
        return False
    _remove_from_threat(game, inv, iid)
    game.state.scenario.vars.get("glimpse_of_the_underworld", {}).pop(investigator_id, None)
    game.damage_engine.deal_damage(investigator_id, damage=1, horror=1)
    controller.log("🕳️ [快速]弃掉【窥看地下世界】，受1伤1恐")
    return True


def activate_discard_threads_of_reality(controller, investigator_id: str) -> bool:
    """[行动]：弃掉你控制的1个支援，弃掉现实之线。

    简化：自动弃掉费用最低的支援（官方由你选择）。
    """
    game = controller.game
    inv = game.state.get_investigator(investigator_id)
    if inv is None or inv.actions_remaining < 1:
        return False
    rec = game.state.scenario.vars.get("threads_of_reality", {}).get(investigator_id)
    if rec is None:
        return False
    candidates = []
    for iid in inv.play_area:
        inst = game.state.get_card_instance(iid)
        cd = game.state.get_card_data(inst.card_id) if inst else None
        if cd is not None and cd.type.value == "asset":
            candidates.append((cd.cost or 0, iid))
    if not candidates:
        return False
    candidates.sort(key=lambda t: t[0])
    inv.actions_remaining -= 1
    game.damage_engine._remove_card_from_play(candidates[0][1])
    game.state.cards_in_play.pop(rec["instance_id"], None)
    game.state.scenario.encounter_discard.append("threads_of_reality")
    game.state.scenario.vars.get("threads_of_reality", {}).pop(investigator_id, None)
    controller.log("🧵 花1行动：弃掉1个支援，弃掉【现实之线】")
    return True


def activate_sickening_webs(controller, investigator_id: str,
                            skill: Skill = Skill.COMBAT) -> bool:
    """[行动]：检定战斗3或敏捷3。成功则弃掉所在地点的恶心蛛网。"""
    game = controller.game
    inv = game.state.get_investigator(investigator_id)
    if inv is None or inv.actions_remaining < 1:
        return False
    iid = controller.location_attachment_instance(inv.location_id, "sickening_webs")
    if iid is None:
        return False
    inv.actions_remaining -= 1

    def _ok(_r):
        controller.detach_card_from_location(iid)
        game.state.scenario.vars.get("sickening_webs", {}).pop(inv.location_id, None)
        controller.log("🕸️ 检定成功，弃掉【恶心蛛网】")

    _run_test_full(game, investigator_id, skill, 3, on_success=_ok)
    return True


def activate_hunted_by_corsairs(controller, investigator_id: str,
                                skill: Skill = Skill.INTELLECT) -> bool:
    """[行动]：检定智力4或敏捷4。成功则弃掉海盗追猎。"""
    game = controller.game
    inv = game.state.get_investigator(investigator_id)
    if inv is None or inv.actions_remaining < 1:
        return False
    if not game.state.scenario.vars.get("hunted_by_corsairs"):
        return False
    inv.actions_remaining -= 1

    def _ok(_r):
        game.state.scenario.vars.pop("hunted_by_corsairs", None)
        game.state.scenario.encounter_discard.append("hunted_by_corsairs")
        controller.log("🏴‍☠️ 检定成功，弃掉【海盗追猎】")

    _run_test_full(game, investigator_id, skill, 4, on_success=_ok)
    return True


def activate_song_of_the_magah_bird(controller, investigator_id: str,
                                    skill: Skill = Skill.WILLPOWER) -> bool:
    """[行动]：检定意志4（抵抗呼唤）或战斗4（驱散鸟群）。成功则弃掉麦格鸟之歌。"""
    game = controller.game
    inv = game.state.get_investigator(investigator_id)
    if inv is None or inv.actions_remaining < 1:
        return False
    iid = controller.location_attachment_instance(inv.location_id, "song_of_the_magah_bird")
    if iid is None:
        return False
    inv.actions_remaining -= 1

    def _ok(_r):
        controller.detach_card_from_location(iid)
        controller.log("🐦 检定成功，弃掉【麦格鸟之歌】")

    _run_test_full(game, investigator_id, skill, 4, on_success=_ok)
    return True


def activate_lunar_patrol(controller, investigator_id: str) -> bool:
    """[行动]：检定敏捷3（甩掉巡逻）。成功则弃掉所在地点的月球巡逻。"""
    game = controller.game
    inv = game.state.get_investigator(investigator_id)
    if inv is None or inv.actions_remaining < 1:
        return False
    iid = controller.location_attachment_instance(inv.location_id, "lunar_patrol")
    if iid is None:
        return False
    inv.actions_remaining -= 1

    def _ok(_r):
        controller.detach_card_from_location(iid)
        controller.log("🌙 检定成功，弃掉【月球巡逻】")

    _run_test_full(game, investigator_id, Skill.AGILITY, 3, on_success=_ok)
    return True


def activate_false_awakening(controller, investigator_id: str,
                             skill: Skill = Skill.WILLPOWER) -> bool:
    """[行动]：检定任意技能(2)，+1/每调查员难度。成功则移出游戏。任何调查员可触发。"""
    game = controller.game
    inv = game.state.get_investigator(investigator_id)
    if inv is None or inv.actions_remaining < 1:
        return False
    rec = game.state.scenario.vars.get("false_awakening") or {}
    if not rec:
        return False
    inv.actions_remaining -= 1
    difficulty = 2 + len(game.state.player_order)

    def _ok(_r):
        for cid in list(rec):
            game.state.scenario.vars.setdefault("removed_from_game", []).append(cid)
        game.state.scenario.vars.pop("false_awakening", None)
        controller.log("⏰ 检定成功，【梦中甦醒】移出游戏")

    _run_test_full(game, investigator_id, skill, difficulty, on_success=_ok)
    return True


def activate_discard_indescribable_apparition(controller, investigator_id: str) -> bool:
    """[行动][行动]：弃掉威胁区中的难以描述的鬼魅。"""
    game = controller.game
    inv = game.state.get_investigator(investigator_id)
    if inv is None or inv.actions_remaining < 2:
        return False
    iid = _threat_copy(game, inv, "indescribable_apparition")
    if iid is None:
        return False
    inv.actions_remaining -= 2
    _remove_from_threat(game, inv, iid)
    game.state.scenario.vars.get("indescribable_apparition", {}).pop(investigator_id, None)
    controller.log("👤 花2行动弃掉【难以描述的鬼魅】")
    return True


def activate_deceptive_memories(controller, investigator_id: str) -> bool:
    """[行动]：检定意志3。成功则弃掉欺骗性记忆。"""
    game = controller.game
    inv = game.state.get_investigator(investigator_id)
    if inv is None or inv.actions_remaining < 1:
        return False
    iid = _threat_copy(game, inv, "deceptive_memories")
    if iid is None:
        return False
    inv.actions_remaining -= 1

    def _ok(_r):
        cur = _threat_copy(game, inv, "deceptive_memories")
        if cur is not None:
            _remove_from_threat(game, inv, cur)
        game.state.scenario.vars.get("deceptive_memories", {}).pop(investigator_id, None)
        controller.log("🧠 检定成功，弃掉【欺骗性记忆】")

    _run_test_full(game, investigator_id, Skill.WILLPOWER, 3, on_success=_ok)
    return True


def activate_restless_journey(controller, investigator_id: str) -> bool:
    """[快速]：弃掉无眠之旅并按版本检定（a智力/b战斗/c敏捷3）；失败密谋+1毁灭。"""
    game = controller.game
    inv = game.state.get_investigator(investigator_id)
    if inv is None:
        return False
    card_id = game.state.scenario.vars.get("restless_journey", {}).get(investigator_id)
    if card_id not in _RESTLESS_JOURNEY_SKILL or card_id not in inv.hand:
        return False
    inv.hand.remove(card_id)
    inv.discard.append(card_id)
    game.state.scenario.vars.get("restless_journey", {}).pop(investigator_id, None)

    def _fail(_r):
        game.state.scenario.doom_on_agenda += 1
        controller._check_agenda_threshold()
        controller.log("🚶 无眠之旅检定失败：密谋+1毁灭")

    _run_test_full(game, investigator_id, _RESTLESS_JOURNEY_SKILL[card_id], 3,
                   on_failure=_fail)
    controller.log(f"🚶 [快速]弃掉【{game.state.card_name(card_id)}】并检定")
    return True


def activate_spinner_in_darkness(controller, investigator_id: str,
                                 skill: Skill = Skill.WILLPOWER) -> bool:
    """[行动]：检定任意技能5。成功则弃掉黑暗中的织网者。"""
    game = controller.game
    inv = game.state.get_investigator(investigator_id)
    if inv is None or inv.actions_remaining < 1:
        return False
    rec = game.state.scenario.vars.get("spinner_in_darkness") or {}
    if not rec:
        return False
    inv.actions_remaining -= 1

    def _ok(_r):
        for enemy_iid, iid in list(rec.items()):
            game.state.cards_in_play.pop(iid, None)
        game.state.scenario.encounter_discard.append("the_spinner_in_darkness")
        game.state.scenario.vars.pop("spinner_in_darkness", None)
        controller.log("🕸️ 检定成功，弃掉【黑暗中的织网者】")

    _run_test_full(game, investigator_id, skill, 5, on_success=_ok)
    return True


def activate_caught_in_a_web(controller, investigator_id: str) -> bool:
    """[行动]：检定战斗3。成功则弃掉陷入网中。"""
    game = controller.game
    inv = game.state.get_investigator(investigator_id)
    if inv is None or inv.actions_remaining < 1:
        return False
    iid = _threat_copy(game, inv, "caught_in_a_web")
    if iid is None:
        return False
    inv.actions_remaining -= 1

    def _ok(_r):
        cur = _threat_copy(game, inv, "caught_in_a_web")
        if cur is not None:
            _remove_from_threat(game, inv, cur)
        game.state.scenario.vars.get("caught_in_a_web", {}).pop(investigator_id, None)
        controller.log("🕸️ 检定成功，弃掉【陷入网中】")

    _run_test_full(game, investigator_id, Skill.COMBAT, 3, on_success=_ok)
    return True
