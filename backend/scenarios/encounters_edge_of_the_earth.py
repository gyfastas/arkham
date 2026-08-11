"""Edge of the Earth encounter treachery resolution.

Called from ScenarioController.resolve_encounter_card as a fallback (wiring
done by the session layer). Each handler returns {"pending": bool, ...} or
None (to continue to the next matcher). Choice cards set
`scenario.vars["pending_choice"]` (with an "investigator_id" field for
multiplayer routing) and are re-entered with `choice=<option_id>`.

Cycle-specific mechanics with no engine support are kept in `scenario.vars`
(documented per card below):

- `location_shelter` / `location_levels` / `location_below`: 地点庇护值、
  高度（level）与"正下方地点"映射，由剧本层注入（引擎的 LocationState 无
  shelter/level 字段）。
- `keys_on_location` / `keys_under_control`: 钥匙计数（引擎无钥匙机制）。
- `seals`: {location_id: {"activated": bool}} 封印（引擎无封印机制）。
- `tekeli_li_deck`: 忒咳哩-哩牌堆（list，顶=index 0）。所有"混洗入牌堆"
  统一走 `_shuffle_tekeli_into_deck`，从而支持同源迷霧的拦截。
- `mirage_cleared`: {location_id: bool} 幻景是否已破除（fatal_mirage 机制）。
- `cards_beneath`: {enemy_instance_id: [card_id]} 敌人底下的牌
  （seeping_nightmare 机制）。

Simplifications (documented per card below):

- 失败检定内的"你必须决定（二选一/三选一）"自动取第一项（通常为按差额受
  恐惧/伤害）；仅显现时的选择（anamnesis/nightmarish_vapors/wuk_wuk_wuk）
  使用 pending_choice。
- Hidden/Peril 卡直接公开结算；Peril 的"不得商议"无意义于数字版。
- frostbitten/possessed 的"自动失败"分支、crumbling_ruins 的钥匙标记
  自动失败、hypothermia 的额外标记揭示：引擎无对应钩子，未强制。
- "不能打出/抽牌"（antarctic_wind）、"不能准备"（miasmatic_torment）、
  交战敌人 +1 战斗/躲避（rise_of_the_elder_things）、战斗/躲避/谈判难度
  +1（abandoned_to_madness）等持续修正：记入 vars，未强制（无修正钩子）。
- 战斗外技能修正仅 whiteout 通过 SKILL_VALUE_DETERMINED 实装。
"""

from __future__ import annotations

import random
from typing import Any

from backend.models.enums import ChaosTokenType, GameEvent, Skill, TimingPriority
from backend.models.state import CardInstance, is_weakness_card

# 标记匹配（数据 traits 为英文；兼容中文与 keywords）
_ELDER_THING_TAGS = ("elder thing", "古老者")
_POSSESSED_TAGS = ("possessed", "附身")
_EXPEDITION_TAGS = ("expedition", "探險")
_PENGUIN_TAGS = ("penguin", "企鵝")
_PENGUIN_IDS = ("giant_albino_penguin",)
_NIGHTMARE_ID = "seeping_nightmare"
_GATE_ID = "the_gate_of_yquaa"

_TEKELI_LI_IDS = (
    "tekeli_li_a", "tekeli_li_b", "tekeli_li_c", "tekeli_li_d",
    "tekeli_li_e", "tekeli_li_f", "tekeli_li_g",
)


# ---------------------------------------------------------------------------
# 通用辅助
# ---------------------------------------------------------------------------

def _margin_fail(result) -> int:
    return max(0, (getattr(result, "difficulty", 0) or 0) - (getattr(result, "modified_skill", 0) or 0))


def _log_names(game, cids: list[str]) -> str:
    return "、".join(game.state.card_name(c) for c in cids)


def _tags_of_card(game, card_id: str) -> list[str]:
    cd = game.state.get_card_data(card_id)
    if cd is None:
        return []
    return list(getattr(cd, "keywords", None) or []) + list(getattr(cd, "traits", None) or [])


def _is_enemy_with_any_tag(game, card_id: str, tags) -> bool:
    cd = game.state.get_card_data(card_id)
    if cd is None or cd.type.value != "enemy":
        return False
    return any(t in _tags_of_card(game, card_id) for t in tags)


def _enemies_with_any_tag(game, tags) -> list[str]:
    out = []
    for iid, inst in game.state.cards_in_play.items():
        cd = game.state.get_card_data(inst.card_id)
        if cd is None or cd.type.value != "enemy":
            continue
        if any(t in _tags_of_card(game, inst.card_id) for t in tags):
            out.append(iid)
    return out


def _place_in_threat(game, inv, card_id: str) -> str:
    inst_id = game.state.next_instance_id()
    game.state.cards_in_play[inst_id] = CardInstance(
        instance_id=inst_id, card_id=card_id,
        owner_id=inv.investigator_id, controller_id=inv.investigator_id,
    )
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


def _nearest_instance(game, inv, iids: list[str]) -> str | None:
    """最近的敌人实例（交战 > 同地点 > 任意）。"""
    for iid in inv.threat_area:
        if iid in iids:
            return iid
    loc = game.state.get_location(inv.location_id)
    if loc:
        for iid in loc.enemies:
            if iid in iids:
                return iid
    return iids[0] if iids else None


def _pull_enemy_by_tags(game, tags) -> str | None:
    """Search encounter deck then discard for an enemy with any of the tags."""
    s = game.state.scenario
    for pile in (s.encounter_deck, s.encounter_discard):
        for cid in list(pile):
            if _is_enemy_with_any_tag(game, cid, tags):
                pile.remove(cid)
                return cid
    return None


def _spawn_engaged(game, card_id: str, inv) -> str:
    iid = game.state.next_instance_id()
    game.state.cards_in_play[iid] = CardInstance(
        instance_id=iid, card_id=card_id,
        owner_id="scenario", controller_id="scenario",
    )
    inv.threat_area.append(iid)
    return iid


def _register_one_shot(game, event: GameEvent, handler) -> None:
    """Register an event handler that unregisters itself after firing once."""
    holder: list[Any] = []

    def _wrap(ctx):
        entry = holder[0]
        game.event_bus.unregister(entry)
        handler(ctx)

    holder.append(game.event_bus.register(event, _wrap, priority=TimingPriority.AFTER))


# ---------------------------------------------------------------------------
# EOE 剧本机制辅助（数据来自 scenario.vars，引擎缺口见模块 docstring）
# ---------------------------------------------------------------------------

def _shelter(game, location_id: str) -> int:
    return int(game.state.scenario.vars.get("location_shelter", {}).get(location_id, 0) or 0)


def _level(game, location_id: str) -> int:
    return int(game.state.scenario.vars.get("location_levels", {}).get(location_id, 0) or 0)


def _location_below(game, location_id: str) -> str | None:
    """正下方地点：优先 vars["location_below"] 映射，否则取相连的更低地点。"""
    below = game.state.scenario.vars.get("location_below", {}).get(location_id)
    if below in game.state.locations:
        return below
    loc = game.state.get_location(location_id)
    here = _level(game, location_id)
    for conn in (loc.connections if loc else []):
        if conn in game.state.locations and _level(game, conn) < here:
            return conn
    return None


def _nearest_location(game, from_location_id: str, predicate) -> str | None:
    """BFS 最近满足条件的地点（含起点）；都不满足时退回任意满足条件的地点。"""
    seen: set[str] = set()
    queue = [from_location_id]
    while queue:
        lid = queue.pop(0)
        if lid in seen:
            continue
        seen.add(lid)
        loc = game.state.get_location(lid)
        if loc is None:
            continue
        if predicate(lid):
            return lid
        queue.extend(c for c in loc.connections if c not in seen)
    for lid in game.state.locations:
        if lid not in seen and predicate(lid):
            return lid
    return None


def _distance_to(game, from_location_id: str, target_location_id: str) -> int | None:
    """BFS 地点距离（经过的地点数）。"""
    if from_location_id == target_location_id:
        return 0
    seen = {from_location_id}
    queue = [(from_location_id, 0)]
    while queue:
        lid, dist = queue.pop(0)
        loc = game.state.get_location(lid)
        for conn in (loc.connections if loc else []):
            if conn in seen or conn not in game.state.locations:
                continue
            if conn == target_location_id:
                return dist + 1
            seen.add(conn)
            queue.append((conn, dist + 1))
    return None


def _gate_location(game) -> str | None:
    """伊誇之门地点：vars["gate_of_yquaa_location"] 优先，否则按 card_id 找。"""
    lid = game.state.scenario.vars.get("gate_of_yquaa_location")
    if lid in game.state.locations:
        return lid
    for loc in game.state.locations.values():
        if loc.card_data.id == _GATE_ID:
            return loc.location_id
    return None


# ---------------------------------------------------------------------------
# 忒咳哩-哩牌堆
# ---------------------------------------------------------------------------

def _tekeli_deck(game) -> list[str]:
    return game.state.scenario.vars.setdefault("tekeli_li_deck", [])


def _kindred_mist_location(game) -> str | None:
    rec = game.state.scenario.vars.get("kindred_mist") or {}
    return rec.get("location_id")


def _shuffle_tekeli_into_deck(controller, inv, n: int) -> int:
    """将忒咳哩-哩牌堆顶 N 张混洗入调查员牌堆（不查看）。返回无法混洗的数量。

    同源迷霧：若调查员位于其被叠加地点，改为抽取那些牌（放入手牌）。
    简化：抽到时不再立即结算其效果（按正常抽到弱点时再结算）。
    """
    game = controller.game
    deck = _tekeli_deck(game)
    km_loc = _kindred_mist_location(game)
    missing = 0
    for _ in range(n):
        if not deck:
            missing += 1
            continue
        cid = deck.pop(0)
        if km_loc is not None and inv.location_id == km_loc:
            inv.hand.append(cid)
            controller.log(f"🌫️ 同源迷霧：改為抽取【{game.state.card_name(cid)}】")
        else:
            inv.deck.append(cid)
            random.shuffle(inv.deck)
            controller.log(f"🐙 【{game.state.card_name(cid)}】混洗入你的牌堆（未查看）")
    return missing


def _resolve_tekeli_li(controller, card_id: str, investigator_id: str,
                       *, return_to_bottom: bool = True) -> None:
    """结算一张忒咳哩-哩弱点的显现效果，然后（默认）放到忒咳哩-哩牌堆底。"""
    game = controller.game
    inv = game.state.get_investigator(investigator_id)
    if inv is None:
        return
    log = controller.log

    if card_id == "tekeli_li_a":
        game.damage_engine.deal_damage(investigator_id, horror=1)
        log("🐙 忒咳哩-哩：受到1恐惧")
    elif card_id == "tekeli_li_b":
        game.damage_engine.deal_damage(investigator_id, damage=1)
        log("🐙 忒咳哩-哩：受到1伤害")
    elif card_id == "tekeli_li_c":
        if inv.hand:
            cid = random.choice(inv.hand)
            inv.hand.remove(cid)
            inv.discard.append(cid)
            log(f"🐙 忒咳哩-哩：随机弃掉【{game.state.card_name(cid)}】")
        else:
            log("🐙 忒咳哩-哩：无手牌可弃")
    elif card_id == "tekeli_li_d":
        lost = min(2, inv.resources)
        inv.resources -= lost
        log(f"🐙 忒咳哩-哩：失去{lost}资源")
    elif card_id == "tekeli_li_e":
        # 简化：以"还有剩余行动"近似"现在是你的回合"
        if inv.actions_remaining > 0:
            inv.actions_remaining -= 1
            log("🐙 忒咳哩-哩：失去1行动")
        else:
            def _on_turn_begin(ctx):
                if ctx.investigator_id != investigator_id:
                    return
                inv.actions_remaining = max(0, inv.actions_remaining - 1)
                log("🐙 忒咳哩-哩：下个回合失去1行动")
            _register_one_shot(game, GameEvent.INVESTIGATOR_TURN_BEGINS, _on_turn_begin)
            log("🐙 忒咳哩-哩：你的下个回合失去1行动")
    elif card_id == "tekeli_li_f":
        loc = game.state.get_location(inv.location_id)
        if inv.clues > 0 and loc is not None:
            inv.clues -= 1
            loc.clues += 1
            log("🐙 忒咳哩-哩：放置1线索到你所在地点")
        else:
            log("🐙 忒咳哩-哩：无线索可放")
    elif card_id == "tekeli_li_g":
        # 简化：自动弃掉第一个支援（官方由你选择）
        if inv.play_area:
            iid = inv.play_area[0]
            inst = game.state.get_card_instance(iid)
            cid = inst.card_id if inst else iid
            game.damage_engine._remove_card_from_play(iid)
            log(f"🐙 忒咳哩-哩：弃掉支援【{game.state.card_name(cid)}】")
        else:
            log("🐙 忒咳哩-哩：无支援可弃")

    if return_to_bottom:
        _tekeli_deck(game).append(card_id)


def _register_frost_token_hit(game, investigator_id: str, *, damage: int = 0,
                              horror: int = 0) -> None:
    """一次性：该调查员下次检定揭示 [frost] 标记时受 1 点伤害/恐惧。

    简化：引擎每次检定只揭示1个标记，故一次性监听即可覆盖"每个[frost]"
    的效果；多次揭示不支持（引擎缺口）。
    """
    holder: list[Any] = []

    def _cleanup():
        for entry in holder:
            game.event_bus.unregister(entry)

    def _on_token(ctx):
        if ctx.investigator_id != investigator_id:
            return
        _cleanup()
        if ctx.chaos_token == ChaosTokenType.FROST:
            game.damage_engine.deal_damage(investigator_id, damage=damage, horror=horror)

    def _on_end(ctx):
        if ctx.investigator_id not in (None, investigator_id):
            return
        _cleanup()

    holder.append(game.event_bus.register(GameEvent.CHAOS_TOKEN_RESOLVED, _on_token,
                                          priority=TimingPriority.AFTER))
    holder.append(game.event_bus.register(GameEvent.SKILL_TEST_ENDS, _on_end,
                                          priority=TimingPriority.AFTER))


def _attach_to_enemy(game, card_id: str, enemy_iid: str) -> str:
    iid = game.state.next_instance_id()
    game.state.cards_in_play[iid] = CardInstance(
        instance_id=iid, card_id=card_id,
        owner_id="scenario", controller_id="scenario",
        attached_to=enemy_iid,
    )
    return iid


def _is_partner_asset(game, instance_id: str) -> bool:
    inst = game.state.get_card_instance(instance_id)
    cd = game.state.get_card_data(inst.card_id) if inst else None
    if cd is None or cd.type.value != "asset":
        return False
    tags = list(getattr(cd, "keywords", None) or []) + list(getattr(cd, "traits", None) or [])
    if "partner" in tags or "夥伴" in tags:
        return True
    # EOE 伙伴卡以 "Partner." 关键词开头（数据未单独抽取为 trait）
    return (cd.text or "").lstrip().lower().startswith("partner")


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

def resolve_treachery(controller, card_id: str, *, investigator_id: str,
                      choice: str | None = None) -> dict | None:
    """结算 Edge of the Earth 遭遇卡。未处理返回 None。"""
    game = controller.game
    inv = game.state.get_investigator(investigator_id)
    if inv is None:
        return None
    log = controller.log
    run_test = controller._run_skill_test
    svars = game.state.scenario.vars

    # ---- Ice and Death ----
    if card_id == "apeirophobia":
        x = _shelter(game, inv.location_id)
        log(f"😱 遭遇：無限恐懼症（意志{x}=地点庇护值，失败三选一）")

        def on_fail(r):
            # 简化：自动选择按差额受恐惧（官方三选一：按差额恐惧 / 放2线索 / 加1[frost]）
            m = _margin_fail(r)
            if m:
                game.damage_engine.deal_damage(investigator_id, horror=m)
        run_test(investigator_id, skill=Skill.WILLPOWER, difficulty=x, on_failure=on_fail)
        return {"pending": False, "message": "apeirophobia"}

    if card_id == "zero_visibility":
        _place_in_threat(game, inv, "zero_visibility")
        # 简化：离开有叠加诡计地点的+1行动额外费用未强制（无费用钩子）
        svars.setdefault("zero_visibility", {})[investigator_id] = True
        holder: list[Any] = []

        def _on_turn_end(ctx):
            if ctx.investigator_id != investigator_id:
                return
            if _threat_copy(game, inv, "zero_visibility") is None:
                game.event_bus.unregister(holder[0])
                return

            def _ok(_r):
                iid = _threat_copy(game, inv, "zero_visibility")
                if iid is not None:
                    _remove_from_threat(game, inv, iid)
                    game.state.scenario.encounter_discard.append("zero_visibility")
                    svars.get("zero_visibility", {}).pop(investigator_id, None)
                    log("🌫️ 零能見度：回合结束敏捷检定成功，弃掉")

            # _run_skill_test 不暴露成功回调，直接调用检定引擎
            game.skill_test_engine.run_test(
                investigator_id=investigator_id, skill_type=Skill.AGILITY,
                difficulty=2, committed_card_ids=[],
                on_success=_ok, on_failure=lambda r: None)

        holder.append(game.event_bus.register(GameEvent.INVESTIGATOR_TURN_ENDS,
                                              _on_turn_end, priority=TimingPriority.AFTER))
        log("🌫️ 遭遇：零能見度——放入威胁区（离开有叠加诡计的地点+1行动[未强制]；"
            "回合结束敏捷2成功则弃掉）")
        return {"pending": False, "message": "zero_visibility"}

    # ---- Seeping Nightmares ----
    if card_id == "phantasmagoria":
        nightmares = [iid for iid, inst in game.state.cards_in_play.items()
                      if inst.card_id == _NIGHTMARE_ID]
        if not nightmares:
            log("🌀 遭遇：千變幻景——场上无滲出夢魘，涌动")
            return {"pending": False, "message": "surge", "surge": True}
        # 简化：以离抽牌调查员最近者为准（官方为离任一调查员最近者）
        target = _nearest_instance(game, inv, nightmares)
        beneath = svars.get("cards_beneath", {}).get(target) or []
        if beneath:
            chosen = random.choice(beneath)
            beneath.remove(chosen)
            loc_id = _enemy_location(game, target)
            loc = game.state.get_location(loc_id) if loc_id else None
            cd = game.state.get_card_data(chosen)
            if loc is not None and cd is not None and cd.type.value == "enemy":
                iid = game.state.next_instance_id()
                game.state.cards_in_play[iid] = CardInstance(
                    instance_id=iid, card_id=chosen,
                    owner_id="scenario", controller_id="scenario")
                loc.enemies.append(iid)
                log(f"🌀 遭遇：千變幻景——【{game.state.card_name(chosen)}】从滲出夢魘底下生成于其地点")
            else:
                # 简化：非敌人/无地点无法生成，放入遭遇弃牌堆
                game.state.scenario.encounter_discard.append(chosen)
                log(f"🌀 遭遇：千變幻景——【{game.state.card_name(chosen)}】无法生成，弃掉")
        else:
            # 简化：直接移至抽牌调查员地点交战并攻击（官方按敌军阶段移动规则）
            inst = game.state.get_card_instance(target)
            if inst is not None:
                inst.exhausted = False
            _engage_investigator(game, target, inv)
            _enemy_attack(game, target, investigator_id)
            log("🌀 遭遇：千變幻景——滲出夢魘底下无牌，移动、交战并立即攻击（不消耗）")
        return {"pending": False, "message": "phantasmagoria"}

    # ---- Fatal Mirage ----
    if card_id == "evanescent_mist":
        cleared = svars.get("mirage_cleared", {})
        loc_id = _nearest_location(game, inv.location_id,
                                   lambda lid: not cleared.get(lid, False))
        if loc_id is None:
            loc_id = inv.location_id
        iid = controller.attach_card_to_location("evanescent_mist", loc_id)
        loc = game.state.get_location(loc_id)
        if loc is not None:
            loc.clues += 2
        # 简化：翻面需额外花2线索/各受2伤害未强制（引擎无幻景翻面机制）；
        # 每轮结束检查幻景是否已破除，是则弃掉
        holder: list[Any] = []

        def _on_round(_ctx):
            if svars.get("mirage_cleared", {}).get(loc_id):
                game.event_bus.unregister(holder[0])
                controller.detach_card_from_location(iid)
                log("🌁 易散之霧：地点已破除幻景，弃掉")

        holder.append(game.event_bus.register(GameEvent.ROUND_ENDS, _on_round,
                                              priority=TimingPriority.AFTER))
        log(f"🌁 遭遇：易散之霧——叠加到【{game.state.card_name(loc.card_data.id) if loc else loc_id}】"
            "并+2线索（翻面额外费用[未强制]；破除幻景后弃掉）")
        return {"pending": False, "message": "evanescent_mist"}

    if card_id == "anamnesis":
        # Peril。注意：官方英文为 2 horror，text_cn 误作"2點傷害"（网络不可用未能
        # 核对 arkhamdb，按英文文本结算）。
        if choice is None:
            svars["pending_choice"] = {
                "card_id": card_id,
                "investigator_id": investigator_id,
                "prompt": "回首往事（禍害）：你必须决定——受2恐惧 或 当前密谋+1毁灭",
                "options": [
                    {"id": "take_horror", "label": "受到2恐惧"},
                    {"id": "place_doom", "label": "当前密谋+1毁灭（可能推进）"},
                ],
            }
            return {"pending": True, "message": "pending_choice"}
        if choice == "place_doom":
            game.state.scenario.doom_on_agenda += 1
            controller._check_agenda_threshold()
            log("🧠 遭遇：回首往事——当前密谋+1毁灭")
        else:
            game.damage_engine.deal_damage(investigator_id, horror=2)
            log("🧠 遭遇：回首往事——受到2恐惧")
        return {"pending": False, "message": "anamnesis"}

    # ---- To the Forbidden Peaks ----
    if card_id == "snowfall":
        loc = game.state.get_location(inv.location_id)
        if loc is not None:
            loc.clues += 2
        log("❄️ 遭遇：降雪——所在地点+2线索（来自供应堆）")
        return {"pending": False, "message": "snowfall"}

    if card_id == "avalanche":
        # 简化：地点高度/正下方地点来自 scenario.vars（引擎无 level 字段）；
        # 初始无法下移即必然整场无法移动 → 直接涌动（官方仍会空转检定，无其他效果）
        lvl0 = _level(game, inv.location_id)
        if not (1 <= lvl0 <= 4) or _location_below(game, inv.location_id) is None:
            log("🌨️ 遭遇：雪崩——无法向下移动，涌动")
            return {"pending": False, "message": "surge", "surge": True}
        log("🌨️ 遭遇：雪崩（下移后意志X=地点高度，失败重复；安全上限10轮）")
        state = {"cycles": 0}

        def _cycle():
            state["cycles"] += 1
            lvl = _level(game, inv.location_id)
            if 1 <= lvl <= 4:
                below = _location_below(game, inv.location_id)
                if below is not None:
                    inv.location_id = below
                    log(f"  → 你坠落到【{game.state.locations[below].card_data.name_cn}】")
            x = _level(game, inv.location_id)

            def on_fail(_r):
                if state["cycles"] < 10:
                    _cycle()
            run_test(investigator_id, skill=Skill.WILLPOWER, difficulty=x, on_failure=on_fail)

        _cycle()
        return {"pending": False, "message": "avalanche"}

    if card_id == "hanging_on_the_edge":
        log("🧗 遭遇：懸於邊緣（敏捷3，失败受2伤害、探險支援掉落到地点、下移）")

        def on_fail(r):
            game.damage_engine.deal_damage(investigator_id, damage=2)
            dropped = []
            for iid in list(inv.play_area):
                inst = game.state.get_card_instance(iid)
                if inst is None:
                    continue
                if any(t in _tags_of_card(game, inst.card_id) for t in _EXPEDITION_TAGS):
                    game.damage_engine._remove_card_from_play(iid)
                    dropped.append(inst.card_id)
            if dropped:
                # 简化：掉落到地点的探險支援记入 vars（引擎无"地点上的支援"区域）
                svars.setdefault("dropped_expedition_assets", {}).setdefault(
                    inv.location_id, []).extend(dropped)
                log(f"  → 探險支援【{_log_names(game, dropped)}】掉落到所在地点")
            below = _location_below(game, inv.location_id)
            if below is not None:
                inv.location_id = below
                log(f"  → 你坠落到【{game.state.locations[below].card_data.name_cn}】")
        run_test(investigator_id, skill=Skill.AGILITY, difficulty=3, on_failure=on_fail)
        return {"pending": False, "message": "hanging_on_the_edge"}

    if card_id == "hypothermia":
        lvl = _level(game, inv.location_id)
        # 简化：高度4-5的"额外揭示1个标记"未强制（引擎无额外揭示钩子）
        extra = "（高度4-5：额外标记[未强制]）" if lvl >= 4 else ""
        log(f"🥶 遭遇：低溫症（意志3，失败：加1[frost] 或 按差额受恐惧）{extra}")

        def on_fail(r):
            # 简化：自动选择按差额受恐惧（官方二选一）
            m = _margin_fail(r)
            if m:
                game.damage_engine.deal_damage(investigator_id, horror=m)
        run_test(investigator_id, skill=Skill.WILLPOWER, difficulty=3, on_failure=on_fail)
        return {"pending": False, "message": "hypothermia"}

    # ---- City of the Elder Things ----
    if card_id == "dawning_of_the_truth":
        keys = (int(svars.get("keys_on_location", {}).get(inv.location_id, 0) or 0)
                + int(svars.get("keys_under_control", {}).get(investigator_id, 0) or 0))
        difficulty = 2 + keys
        log(f"💡 遭遇：真相開端（意志{difficulty}，失败受2恐惧；差额≥3改受3恐惧）")

        def on_fail(r):
            m = _margin_fail(r)
            game.damage_engine.deal_damage(investigator_id, horror=3 if m >= 3 else 2)
        run_test(investigator_id, skill=Skill.WILLPOWER, difficulty=difficulty, on_failure=on_fail)
        return {"pending": False, "message": "dawning_of_the_truth"}

    if card_id == "crumbling_ruins":
        # 简化：揭示与钥匙一致的标记则自动失败——未强制（引擎无钥匙标记机制）
        log("🏚️ 遭遇：崩塌廢墟（敏捷3，失败按差额受伤害；钥匙标记自动失败[未强制]）")
        run_test(investigator_id, skill=Skill.AGILITY, difficulty=3,
                 on_failure=lambda r: game.damage_engine.deal_damage(
                     investigator_id, damage=_margin_fail(r)))
        return {"pending": False, "message": "crumbling_ruins"}

    if card_id in ("frostbitten", "possessed"):
        is_frostbitten = card_id == "frostbitten"
        kind = "伤害" if is_frostbitten else "恐惧"
        _place_in_threat(game, inv, card_id)
        # 简化：可如1点伤害/恐惧般被治愈——治愈机制无钩子，记入 vars 未强制
        svars.setdefault(card_id, {})[investigator_id] = True
        state = {"used": False}
        holder: list[Any] = []

        def _cleanup_if_gone():
            if _threat_copy(game, inv, card_id) is None:
                for entry in holder:
                    game.event_bus.unregister(entry)
                return True
            return False

        def _on_begin(ctx):
            if ctx.investigator_id == investigator_id:
                state["used"] = False

        def _on_token(ctx):
            if ctx.investigator_id != investigator_id or state["used"]:
                return
            if ctx.chaos_token != ChaosTokenType.FROST:
                return
            if _cleanup_if_gone():
                return
            state["used"] = True
            # 简化：自动选择受1点伤害/恐惧（官方为 受1点 或 本次检定自动失败 二选一）
            if is_frostbitten:
                game.damage_engine.deal_damage(investigator_id, damage=1)
            else:
                game.damage_engine.deal_damage(investigator_id, horror=1)
            log(f"🧊 【{game.state.card_name(card_id)}】：揭示[frost]，受1{kind}（每次检定限1次）")

        holder.append(game.event_bus.register(GameEvent.SKILL_TEST_BEGINS, _on_begin,
                                              priority=TimingPriority.AFTER))
        holder.append(game.event_bus.register(GameEvent.CHAOS_TOKEN_RESOLVED, _on_token,
                                              priority=TimingPriority.AFTER))
        log(f"🧊 遭遇：{game.state.card_name(card_id)}——放入威胁区（揭示[frost]时受1{kind}"
            "或自动失败[取前者]；治愈[未强制]）")
        return {"pending": False, "message": card_id}

    # ---- The Heart of Madness ----
    if card_id in ("primeval_terror", "roots_of_the_earth"):
        is_terror = card_id == "primeval_terror"
        gate = _gate_location(game)
        dist = _distance_to(game, inv.location_id, gate) if gate else None
        difficulty = 2 + (dist or 0)
        skill = Skill.WILLPOWER if is_terror else Skill.AGILITY
        name = "原始恐怖" if is_terror else "地球根源"
        log(f"🌋 遭遇：{name}（{'意志' if is_terror else '敏捷'}{difficulty}=2+距伊誇之门"
            f"{dist or 0}，失败受2{'恐惧' if is_terror else '伤害'}）")

        def on_fail(r):
            if is_terror:
                game.damage_engine.deal_damage(investigator_id, horror=2)
            else:
                game.damage_engine.deal_damage(investigator_id, damage=2)
        run_test(investigator_id, skill=skill, difficulty=difficulty, on_failure=on_fail)
        return {"pending": False, "message": card_id}

    # ---- The Great Seal ----
    if card_id == "electrostatic_discharge":
        seals = svars.get("seals", {})
        hits = 0
        for other_id in list(game.state.player_order):
            other = game.state.get_investigator(other_id)
            if other is None or other.is_defeated:
                continue
            seal = seals.get(other.location_id)
            if seal is None:
                continue
            hits += 1
            game.damage_engine.deal_damage(
                other_id, horror=1, damage=1 if seal.get("activated") else 0)
        log(f"⚡ 遭遇：靜電釋放——{hits} 位调查员位于封印地点，受1恐惧"
            "（封印已啟動再受1伤害）；涌动")
        return {"pending": False, "message": "surge", "surge": True}

    # ---- Agents of the Unknown ----
    if card_id == "the_madness_within":
        log("🧠 遭遇：潛藏的瘋狂（意志4，失败按差额将忒咳哩-哩牌堆顶混洗入你的牌堆）")

        def on_fail(r):
            m = _margin_fail(r)
            if m <= 0:
                return
            missing = _shuffle_tekeli_into_deck(controller, inv, m)
            if missing:
                game.damage_engine.deal_damage(investigator_id, horror=missing)
                log(f"  → {missing} 张无法混洗，受{missing}恐惧")
        run_test(investigator_id, skill=Skill.WILLPOWER, difficulty=4, on_failure=on_fail)
        return {"pending": False, "message": "the_madness_within"}

    # ---- Creatures in the Ice ----
    if card_id == "kindred_mist":
        loc_id = _nearest_location(
            game, inv.location_id,
            lambda lid: controller.location_attachment_instance(lid, "kindred_mist") is None)
        if loc_id is None:
            loc_id = inv.location_id
        iid = controller.attach_card_to_location("kindred_mist", loc_id)
        svars["kindred_mist"] = {"location_id": loc_id}

        def _on_round(_ctx):
            controller.detach_card_from_location(iid)
            svars.pop("kindred_mist", None)
            log("🌫️ 同源迷霧：本轮结束，弃掉")

        _register_one_shot(game, GameEvent.ROUND_ENDS, _on_round)
        log("🌫️ 遭遇：同源迷霧——叠加到最近地点（该处的忒咳哩-哩混洗改为抽取；轮末弃掉）")
        return {"pending": False, "message": "kindred_mist"}

    # ---- Deadly Weather ----
    if card_id == "antarctic_wind":
        loc_id = _nearest_location(
            game, inv.location_id,
            lambda lid: controller.location_attachment_instance(lid, "antarctic_wind") is None)
        if loc_id is None:
            loc_id = inv.location_id
        iid = controller.attach_card_to_location("antarctic_wind", loc_id)
        # 简化：不能打出/抽牌未强制（无打出/抽牌拦截钩子）
        svars.setdefault("antarctic_wind", {})[loc_id] = True

        def _on_round(_ctx):
            controller.detach_card_from_location(iid)
            svars.get("antarctic_wind", {}).pop(loc_id, None)
            log("🌬️ 南極寒風：本轮结束，弃掉")

        _register_one_shot(game, GameEvent.ROUND_ENDS, _on_round)
        log("🌬️ 遭遇：南極寒風——叠加到最近地点（该地点调查员不能打出/抽牌[未强制]；轮末弃掉）")
        return {"pending": False, "message": "antarctic_wind"}

    if card_id == "whiteout":
        attached_loc = inv.location_id
        iid = controller.attach_card_to_location("whiteout", attached_loc)
        holder: list[Any] = []

        def _on_skill(ctx):
            if ctx.investigator_id is None:
                return
            other = game.state.get_investigator(ctx.investigator_id)
            if other is not None and other.location_id == attached_loc:
                ctx.modify_amount(-1, "whiteout")

        def _on_round(_ctx):
            game.event_bus.unregister(holder[0])
            controller.detach_card_from_location(iid)
            log("🌨️ 雪盲危機：本轮结束，弃掉")

        holder.append(game.event_bus.register(GameEvent.SKILL_VALUE_DETERMINED, _on_skill,
                                              priority=TimingPriority.AFTER))
        _register_one_shot(game, GameEvent.ROUND_ENDS, _on_round)
        log("🌨️ 遭遇：雪盲危機——叠加到所在地点（该地点调查员全技能-1；轮末弃掉）")
        return {"pending": False, "message": "whiteout"}

    if card_id == "polar_vortex":
        attached_loc = inv.location_id
        iid = controller.attach_card_to_location("polar_vortex", attached_loc)
        holder: list[Any] = []

        def _on_turn_end(ctx):
            other = game.state.get_investigator(ctx.investigator_id)
            if other is None or other.location_id != attached_loc:
                return
            game.damage_engine.deal_damage(ctx.investigator_id, damage=1, direct=True)
            # 简化：支援的直接伤害直接累加，不触发支援败北结算
            for aid in other.play_area:
                inst = game.state.get_card_instance(aid)
                cd = game.state.get_card_data(inst.card_id) if inst else None
                if cd is not None and cd.health is not None:
                    inst.damage += 1
            log(f"🌀 極地旋渦：【{ctx.investigator_id}】在被叠加地点结束回合，"
                "其控制的有生命值卡牌各受1直接伤害")

        def _on_round(_ctx):
            game.event_bus.unregister(holder[0])
            controller.detach_card_from_location(iid)
            log("🌀 極地旋渦：本轮结束，弃掉")

        holder.append(game.event_bus.register(GameEvent.INVESTIGATOR_TURN_ENDS, _on_turn_end,
                                              priority=TimingPriority.AFTER))
        _register_one_shot(game, GameEvent.ROUND_ENDS, _on_round)
        log("🌀 遭遇：極地旋渦——叠加到所在地点（回合结束时其有生命值卡牌各受1直接伤害；轮末弃掉）")
        return {"pending": False, "message": "polar_vortex"}

    # ---- Elder Things ----
    if card_id == "rise_of_the_elder_things":
        found = None
        # 遭遇弃牌堆顶 = 最近弃掉的一张（list 末尾）
        for cid in reversed(game.state.scenario.encounter_discard):
            if _is_enemy_with_any_tag(game, cid, _ELDER_THING_TAGS):
                found = cid
                break
        if found is None:
            log("🦑 遭遇：古老者崛起——遭遇弃牌堆无古老者敌人，涌动")
            return {"pending": False, "message": "surge", "surge": True}
        game.state.scenario.encounter_discard.remove(found)
        controller._spawn_enemy_from_encounter(found, investigator_id)
        # 简化：交战古老者 +1战斗/+1躲避直到轮末——记入 vars，未强制（无战斗值修正钩子）
        svars["rise_of_the_elder_things_round"] = game.state.scenario.round_number
        log(f"🦑 遭遇：古老者崛起——【{game.state.card_name(found)}】生成并与你交战"
            "（交战古老者+1战斗/+1躲避[未强制]）")
        return {"pending": False, "message": "rise_of_the_elder_things"}

    # ---- Hazards of Antarctica ----
    if card_id == "ice_shaft":
        log("🕳️ 遭遇：冰井（敏捷3，每个[frost]受1伤害，失败受2伤害）")
        _register_frost_token_hit(game, investigator_id, damage=1)
        run_test(investigator_id, skill=Skill.AGILITY, difficulty=3,
                 on_failure=lambda r: game.damage_engine.deal_damage(investigator_id, damage=2))
        return {"pending": False, "message": "ice_shaft"}

    if card_id == "through_the_ice":
        loc_id = _nearest_location(
            game, inv.location_id,
            lambda lid: controller.location_attachment_instance(lid, "through_the_ice") is None)
        if loc_id is None:
            loc_id = inv.location_id
        iid = controller.attach_card_to_location("through_the_ice", loc_id)
        attached_loc = loc_id
        holder: list[Any] = []

        def _on_move(ctx):
            if controller.location_attachment_instance(attached_loc, "through_the_ice") is None:
                game.event_bus.unregister(holder[0])
                return
            moving = game.state.get_investigator(ctx.investigator_id)
            if moving is None:
                return
            origin, dest = moving.location_id, ctx.location_id
            if origin == dest or attached_loc not in (origin, dest):
                return

            def on_fail(_r):
                # 简化：取消移动未强制（AFTER 优先级无法取消动作）
                game.damage_engine.deal_damage(ctx.investigator_id, damage=1, horror=1)
                controller.detach_card_from_location(iid)
                log(f"🧊 穿越冰雪：【{ctx.investigator_id}】敏捷检定失败，受1伤害1恐惧，弃掉穿越冰雪")
            run_test(ctx.investigator_id, skill=Skill.AGILITY, difficulty=2, on_failure=on_fail)

        holder.append(game.event_bus.register(GameEvent.MOVE_ACTION_INITIATED, _on_move,
                                              priority=TimingPriority.AFTER))
        log("🧊 遭遇：穿越冰雪——叠加到最近地点（进/出需敏捷2，失败受1伤1恐并弃掉"
            "[取消移动未强制]）")
        return {"pending": False, "message": "through_the_ice"}

    # ---- Left Behind ----
    if card_id == "abandoned_to_madness":
        possessed = _enemies_with_any_tag(game, _POSSESSED_TAGS)
        target = _nearest_instance(game, inv, possessed)
        if target is None:
            pulled = _pull_enemy_by_tags(game, _POSSESSED_TAGS)
            if pulled is not None:
                target = _spawn_engaged(game, pulled, inv)
                random.shuffle(game.state.scenario.encounter_deck)
                log(f"😈 遭遇：身陷瘋狂——从遭遇牌堆/弃牌堆抽出【{game.state.card_name(pulled)}】并交战")
        if target is None:
            log("😈 遭遇：身陷瘋狂——找不到附身敌人，无效果")
            return {"pending": False, "message": "abandoned_to_madness"}
        _attach_to_enemy(game, "abandoned_to_madness", target)
        inst = game.state.get_card_instance(target)
        if inst is not None:
            inst.doom += 1
        controller._check_agenda_threshold()
        # 简化：攻击/躲避/谈判该敌人难度+1 记入 vars，未强制（无难度修正钩子）
        svars["abandoned_to_madness"] = {"enemy": target}
        log(f"😈 遭遇：身陷瘋狂——叠加到【{game.state.card_name(inst.card_id if inst else target)}】"
            "并+1毁灭（对其战斗/躲避/谈判难度+1[未强制]）")
        return {"pending": False, "message": "abandoned_to_madness"}

    # ---- Nameless Horrors ----
    if card_id == "blasphemous_visions":
        _shuffle_tekeli_into_deck(controller, inv, 1)
        _place_in_threat(game, inv, "blasphemous_visions")
        # 简化：抽取的忒咳哩-哩弱点额外结算一次——记入 vars，未强制（无抽牌拦截钩子）
        svars.setdefault("blasphemous_visions", {})[investigator_id] = True
        log("👁️ 遭遇：瀆神幻象——忒咳哩-哩顶1张混洗入牌堆，放入威胁区"
            "（抽到的忒咳哩-哩额外结算[未强制]；可用 activate_discard_blasphemous_visions 意志3弃掉）")
        return {"pending": False, "message": "blasphemous_visions"}

    if card_id == "glimpse_the_unspeakable":
        # Peril。简化：混洗入"任意一位调查员"的牌堆 → 取你自己
        deck = _tekeli_deck(game)
        if not deck:
            log("🔮 遭遇：窺看不可說之事——忒咳哩-哩牌堆为空，涌动")
            return {"pending": False, "message": "surge", "surge": True}
        cid = deck.pop(0)
        log(f"🔮 遭遇：窺看不可說之事——抽取【{game.state.card_name(cid)}】并结算")
        _resolve_tekeli_li(controller, cid, investigator_id, return_to_bottom=False)
        inv.deck.append(cid)
        random.shuffle(inv.deck)
        log("  → 结算后混洗入你的牌堆（不放到忒咳哩-哩牌堆底）")
        return {"pending": False, "message": "glimpse_the_unspeakable"}

    if card_id == "nightmarish_vapors":
        # Peril
        if choice is None:
            svars["pending_choice"] = {
                "card_id": card_id,
                "investigator_id": investigator_id,
                "prompt": "噩夢煙氣（禍害）：你必须决定——失去2行动 或 忒咳哩-哩顶2张混洗入你的牌堆",
                "options": [
                    {"id": "lose_actions", "label": "失去2个行动"},
                    {"id": "shuffle_2", "label": "忒咳哩-哩牌堆顶2张混洗入你的牌堆（不查看）"},
                ],
            }
            return {"pending": True, "message": "pending_choice"}
        if choice == "shuffle_2":
            _shuffle_tekeli_into_deck(controller, inv, 2)
            log("🌫️ 遭遇：噩夢煙氣——忒咳哩-哩牌堆顶2张混洗入你的牌堆")
        else:
            lost = min(2, inv.actions_remaining)
            inv.actions_remaining -= lost
            log(f"🌫️ 遭遇：噩夢煙氣——失去{lost}个行动")
        return {"pending": False, "message": "nightmarish_vapors"}

    # ---- Miasma ----
    if card_id == "miasmatic_torment":
        # 注意：text_cn 多出"禍害"二字而英文文本无 Peril（网络不可用未能核对
        # arkhamdb，按英文文本结算）。
        partners = [iid for iid in inv.play_area if _is_partner_asset(game, iid)]
        if not partners:
            log("☣️ 遭遇：瘴氣折磨——无夥伴支援，涌动")
            return {"pending": False, "message": "surge", "surge": True}
        # 简化：自动取第一个夥伴（官方由你选择）
        target = partners[0]
        inst = game.state.get_card_instance(target)
        if inst is not None:
            inst.exhausted = True
        _attach_to_enemy(game, "miasmatic_torment", target)  # 附加到支援实例
        # 简化：被附加支援不能准备——记入 vars，未强制（无准备拦截钩子）
        svars["miasmatic_torment"] = {"asset": target, "investigator_id": investigator_id}
        holder: list[Any] = []

        def _on_turn_end(ctx):
            if ctx.investigator_id != investigator_id:
                return
            asset = game.state.get_card_instance(target)
            if asset is None:
                game.event_bus.unregister(holder[0])
                return
            # 简化：自动优先受1伤害（有生命值时），否则1恐惧（官方二选一）
            cd = game.state.get_card_data(asset.card_id)
            if cd is not None and cd.health is not None:
                asset.damage += 1
                log("☣️ 瘴氣折磨：回合结束，被叠加的夥伴受1伤害")
            else:
                asset.horror += 1
                log("☣️ 瘴氣折磨：回合结束，被叠加的夥伴受1恐惧")

        holder.append(game.event_bus.register(GameEvent.INVESTIGATOR_TURN_ENDS,
                                              _on_turn_end, priority=TimingPriority.AFTER))
        log(f"☣️ 遭遇：瘴氣折磨——消耗并叠加到【{game.state.card_name(inst.card_id if inst else target)}】"
            "（不能准备[未强制]；回合结束受1伤害/恐惧；可用 activate_discard_miasmatic_torment 检定弃掉）")
        return {"pending": False, "message": "miasmatic_torment"}

    if card_id == "nebulous_miasma":
        attached_loc = inv.location_id
        iid = controller.attach_card_to_location("nebulous_miasma", attached_loc)
        holder: list[Any] = []

        def _on_turn_end(ctx):
            other = game.state.get_investigator(ctx.investigator_id)
            if other is None or other.location_id != attached_loc:
                return
            game.damage_engine.deal_damage(ctx.investigator_id, horror=1, direct=True)
            # 简化：支援的直接恐惧直接累加，不触发支援败北结算
            for aid in other.play_area:
                inst = game.state.get_card_instance(aid)
                cd = game.state.get_card_data(inst.card_id) if inst else None
                if cd is not None and cd.sanity is not None:
                    inst.horror += 1
            log(f"☁️ 朦朧瘴氣：【{ctx.investigator_id}】在被叠加地点结束回合，"
                "其控制的有神智值卡牌各受1直接恐惧")

        def _on_round(_ctx):
            game.event_bus.unregister(holder[0])
            controller.detach_card_from_location(iid)
            log("☁️ 朦朧瘴氣：本轮结束，弃掉")

        holder.append(game.event_bus.register(GameEvent.INVESTIGATOR_TURN_ENDS, _on_turn_end,
                                              priority=TimingPriority.AFTER))
        _register_one_shot(game, GameEvent.ROUND_ENDS, _on_round)
        log("☁️ 遭遇：朦朧瘴氣——叠加到所在地点（回合结束时其有神智值卡牌各受1直接恐惧；轮末弃掉）")
        return {"pending": False, "message": "nebulous_miasma"}

    # ---- Penguins ----
    if card_id == "wuk_wuk_wuk":
        penguins = [iid for iid, inst in game.state.cards_in_play.items()
                    if inst.card_id in _PENGUIN_IDS
                    or any(t in _tags_of_card(game, inst.card_id) for t in _PENGUIN_TAGS)]
        penguins = [iid for iid in penguins
                    if game.state.get_card_data(game.state.get_card_instance(iid).card_id) is not None
                    and game.state.get_card_data(game.state.get_card_instance(iid).card_id).type.value == "enemy"]
        if not penguins:
            pulled = None
            s = game.state.scenario
            for pile in (s.encounter_deck, s.encounter_discard):
                for cid in list(pile):
                    if cid in _PENGUIN_IDS or _is_enemy_with_any_tag(game, cid, _PENGUIN_TAGS):
                        pile.remove(cid)
                        pulled = cid
                        break
                if pulled:
                    break
            if pulled is not None:
                controller._spawn_enemy_from_encounter(pulled, investigator_id)
                random.shuffle(game.state.scenario.encounter_deck)
                log(f"🐧 遭遇：嗚啊！嗚啊！嗚啊！——抽出【{game.state.card_name(pulled)}】并交战")
            else:
                log("🐧 遭遇：嗚啊！嗚啊！嗚啊！——找不到巨型白化企鵝，无效果")
            return {"pending": False, "message": "wuk_wuk_wuk"}
        # 简化：最远的企鵝 → 优先不在你地点者，否则第一个
        loc = game.state.get_location(inv.location_id)
        at_loc = [iid for iid in penguins
                  if (loc is not None and iid in loc.enemies) or iid in inv.threat_area]
        target = ([iid for iid in penguins if iid not in at_loc] or penguins)[0]
        if choice is None:
            svars["pending_choice"] = {
                "card_id": card_id,
                "investigator_id": investigator_id,
                "target": target,
                "prompt": "嗚啊！嗚啊！嗚啊！：你必须决定——将巨型白化企鵝移到你所在地点 或 在其上放1毁灭",
                "options": [
                    {"id": "move", "label": "将其移动到你所在地点"},
                    {"id": "place_doom", "label": "在其上放置1毁灭"},
                ],
            }
            return {"pending": True, "message": "pending_choice"}
        target = (svars.get("pending_choice", {}) or {}).get("target", target)
        if target not in game.state.cards_in_play:
            target = penguins[0]
        inst = game.state.get_card_instance(target)
        if choice == "place_doom":
            if inst is not None:
                inst.doom += 1
            controller._check_agenda_threshold()
            log(f"🐧 遭遇：嗚啊！嗚啊！嗚啊！——【{game.state.card_name(inst.card_id if inst else target)}】+1毁灭")
        else:
            for l in game.state.locations.values():
                if target in l.enemies:
                    l.enemies.remove(target)
            for other in game.state.investigators.values():
                if target in other.threat_area:
                    other.threat_area.remove(target)
            if loc is not None:
                loc.enemies.append(target)
            log(f"🐧 遭遇：嗚啊！嗚啊！嗚啊！——【{game.state.card_name(inst.card_id if inst else target)}】移到你所在地点")
        return {"pending": False, "message": "wuk_wuk_wuk"}

    # ---- Silence and Mystery ----
    if card_id == "polar_mirage":
        loc_id = _nearest_location(
            game, inv.location_id,
            lambda lid: (game.state.get_location(lid) is not None
                         and game.state.get_location(lid).clues >= 1
                         and controller.location_attachment_instance(lid, "polar_mirage") is None))
        if loc_id is None:
            # 无有效地点：无法叠加，直接弃掉（不涌动；卡面无 surge）
            game.state.scenario.encounter_discard.append("polar_mirage")
            log("🏜️ 遭遇：極地幻景——无有线索且无叠加的地点，弃掉")
            return {"pending": False, "message": "polar_mirage"}
        iid = controller.attach_card_to_location("polar_mirage", loc_id)
        attached_loc = loc_id
        holder: list[Any] = []

        def _on_clue(ctx):
            if ctx.location_id != attached_loc:
                return
            victim = game.state.get_investigator(ctx.investigator_id)
            if victim is None:
                return
            game.event_bus.unregister(holder[0])
            dropped = []
            for cid in list(victim.hand):
                if is_weakness_card(game.state.get_card_data(cid)):
                    continue
                victim.hand.remove(cid)
                victim.discard.append(cid)
                dropped.append(cid)
            controller.detach_card_from_location(iid)
            log(f"🏜️ 極地幻景：发现线索——弃掉手牌【{_log_names(game, dropped)}】，弃掉極地幻景"
                if dropped else "🏜️ 極地幻景：发现线索——无非弱点手牌，弃掉極地幻景")

        # 简化：仅挂钩"发现线索"（CLUE_DISCOVERED）；"取得线索控制权"无独立事件
        holder.append(game.event_bus.register(GameEvent.CLUE_DISCOVERED, _on_clue,
                                              priority=TimingPriority.AFTER))
        log("🏜️ 遭遇：極地幻景——叠加到最近有线索地点（在该地点发现线索后弃掉你全部非弱点手牌）")
        return {"pending": False, "message": "polar_mirage"}

    if card_id == "dark_aurora":
        log("🌌 遭遇：黑暗極光（意志3，每个[frost]受1恐惧，失败受2恐惧）")
        _register_frost_token_hit(game, investigator_id, horror=1)
        run_test(investigator_id, skill=Skill.WILLPOWER, difficulty=3,
                 on_failure=lambda r: game.damage_engine.deal_damage(investigator_id, horror=2))
        return {"pending": False, "message": "dark_aurora"}

    # ---- Tekeli-li 弱点 ----
    if card_id in _TEKELI_LI_IDS:
        _resolve_tekeli_li(controller, card_id, investigator_id)
        return {"pending": False, "message": card_id}

    return None


# ---------------------------------------------------------------------------
# 公开激活方法（持续卡的 [行动] 能力；供 session 层/测试调用）
# ---------------------------------------------------------------------------

def activate_discard_blasphemous_visions(controller, investigator_id: str) -> bool:
    """[行动]：意志(3)。成功则弃掉威胁区中的瀆神幻象。"""
    game = controller.game
    inv = game.state.get_investigator(investigator_id)
    if inv is None or inv.actions_remaining < 1:
        return False
    iid = _threat_copy(game, inv, "blasphemous_visions")
    if iid is None:
        return False
    inv.actions_remaining -= 1

    def _ok(_r):
        _remove_from_threat(game, inv, iid)
        game.state.scenario.encounter_discard.append("blasphemous_visions")
        game.state.scenario.vars.get("blasphemous_visions", {}).pop(investigator_id, None)
        controller.log("👁️ 意志检定成功，弃掉【瀆神幻象】")

    # _run_skill_test 不暴露成功回调，直接调用检定引擎
    game.skill_test_engine.run_test(
        investigator_id=investigator_id, skill_type=Skill.WILLPOWER,
        difficulty=3, committed_card_ids=[],
        on_success=_ok, on_failure=lambda r: None)
    return True


def activate_discard_miasmatic_torment(controller, investigator_id: str,
                                       *, skill: Skill = Skill.WILLPOWER) -> bool:
    """[行动]：意志或智力(3)。成功则弃掉瘴氣折磨（从被叠加的支援上移除）。"""
    game = controller.game
    inv = game.state.get_investigator(investigator_id)
    if inv is None or inv.actions_remaining < 1:
        return False
    if skill not in (Skill.WILLPOWER, Skill.INTELLECT):
        return False
    rec = game.state.scenario.vars.get("miasmatic_torment") or {}
    if rec.get("investigator_id") != investigator_id:
        return False
    inv.actions_remaining -= 1

    def _ok(_r):
        asset_iid = rec.get("asset")
        for iid, inst in list(game.state.cards_in_play.items()):
            if inst.card_id == "miasmatic_torment" and inst.attached_to == asset_iid:
                game.state.cards_in_play.pop(iid, None)
                game.state.scenario.encounter_discard.append("miasmatic_torment")
        game.state.scenario.vars.pop("miasmatic_torment", None)
        controller.log("☣️ 检定成功，弃掉【瘴氣折磨】")

    # _run_skill_test 不暴露成功回调，直接调用检定引擎
    game.skill_test_engine.run_test(
        investigator_id=investigator_id, skill_type=skill,
        difficulty=3, committed_card_ids=[],
        on_success=_ok, on_failure=lambda r: None)
    return True
