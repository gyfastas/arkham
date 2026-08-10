"""Path to Carcosa encounter treachery resolution.

Called from ScenarioController.resolve_encounter_card as a fallback before the
Dunwich branch. Each handler returns {"pending": bool, "message": str} or None
(to continue to the next matcher). Choice cards set
`scenario.vars["pending_choice"]` (with an "investigator_id" field for
multiplayer routing) and are re-entered with `choice=<option_id>`.

Simplifications (documented per card below):

- Hidden/Peril cards (whispers_in_your_head_a-d, gift_of_madness_a-b,
  possession_a-c, ...): the digital version cannot keep secrets, so the card
  is added to the hand openly. Their ongoing restrictions are recorded in
  `scenario.vars` and NOT enforced by the engine (no hook points); each
  card's [action] discard ability is exposed as a public `activate_*`
  function in this module for the session layer / tests to call.
- "You must either X or Y" choices that happen *inside* a failed skill test
  resolve deterministically (documented per card); only revelation-time
  choices (led_astray, fine_dining) use pending_choice.
- Doubt/Conviction campaign track: read from `scenario.vars["doubt"]` /
  `scenario.vars["conviction"]` (injected by the campaign layer; default 0).
- The Man in the Pallid Mask in-play check uses card_id
  "the_man_in_the_pallid_mask".
- "Set-aside Monster enemies" come from `scenario.vars["set_aside_monsters"]`;
  cards placed beneath the act deck are recorded in
  `scenario.vars["under_scenario_deck"]`.
- Carcosa encounter data stores traits in English while the core keyword
  derivation maps Chinese traits, so trait checks here scan both
  `keywords` and `traits`.
"""

from __future__ import annotations

import random
from typing import Any

from backend.engine.event_bus import EventContext
from backend.models.enums import GameEvent, Skill, SlotType, TimingPriority
from backend.models.state import CardInstance

# ---------------------------------------------------------------------------
# Hidden 卡限制标记（scenario.vars 记录；引擎暂无拦截点，未强制）
# ---------------------------------------------------------------------------
_WHISPERS_RESTRICTION = {
    "whispers_in_your_head_a": "no_skill_commit",   # 不能投入技能卡
    "whispers_in_your_head_b": "move_once_per_turn",  # 每回合最多移动1次
    "whispers_in_your_head_c": "no_fast",           # 不能触发快速能力
    "whispers_in_your_head_d": "no_events",         # 不能打出事件
}


def _margin_fail(result) -> int:
    return max(0, (getattr(result, "difficulty", 0) or 0) - (getattr(result, "modified_skill", 0) or 0))


def _log_names(game, cids: list[str]) -> str:
    return "、".join(game.state.card_name(c) for c in cids)


def _tags_of(game, instance_id: str) -> list[str]:
    """Enemy keyword+trait union (carcosa data keeps English traits)."""
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


def _pull_enemy_from_encounter(game, tag: str) -> str | None:
    """Search encounter deck then discard for an enemy with the tag."""
    s = game.state.scenario
    for pile in (s.encounter_deck, s.encounter_discard):
        for cid in list(pile):
            if _is_enemy_with_tag(game, cid, tag):
                pile.remove(cid)
                return cid
    return None


def _shroud_of(controller, location_id: str) -> int:
    loc = controller.game.state.get_location(location_id)
    if loc is None:
        return 0
    return (loc.shroud or 0) + controller.location_shroud_bonus(location_id)


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


def _auto_discard_assets(controller, inv, x: int, *, item_only: bool) -> list[str]:
    """Greedy-discard cheapest assets (play area first, then hand) until the
    total printed cost reaches X. Auto-selection simplification: officially
    the investigator chooses which cards to discard."""
    game = controller.game
    if x <= 0:
        return []
    candidates: list[tuple[int, str, str]] = []  # (cost, where, ref)
    for iid in inv.play_area:
        inst = game.state.get_card_instance(iid)
        cd = game.state.get_card_data(inst.card_id) if inst else None
        if cd is None or cd.type.value != "asset":
            continue
        if item_only and not _is_item(cd):
            continue
        candidates.append((cd.cost or 0, "play", iid))
    for cid in inv.hand:
        cd = game.state.get_card_data(cid)
        if cd is None or cd.type.value != "asset":
            continue
        if item_only and not _is_item(cd):
            continue
        candidates.append((cd.cost or 0, "hand", cid))
    candidates.sort(key=lambda t: t[0])
    discarded: list[str] = []
    total = 0
    for cost, where, ref in candidates:
        if total >= x:
            break
        if where == "play":
            inst = game.state.get_card_instance(ref)
            cid = inst.card_id if inst else ref
            game.damage_engine._remove_card_from_play(ref)
        else:
            cid = ref
            inv.hand.remove(ref)
            inv.discard.append(ref)
        discarded.append(cid)
        total += cost
    return discarded


def _is_item(cd) -> bool:
    traits = list(getattr(cd, "traits", None) or []) + list(getattr(cd, "keywords", None) or [])
    return "item" in traits or "道具" in traits


def _pallid_mask_in_play(game) -> str | None:
    for iid, inst in game.state.cards_in_play.items():
        if inst.card_id == "the_man_in_the_pallid_mask":
            return iid
    return None


def _agenda_act_level(game) -> int:
    """1/2/3 from current agenda; act 3a forces 3 (crashing_floods/worlds_merge)."""
    s = game.state.scenario
    if s.current_act_index >= 2 or s.current_agenda_index >= 2:
        return 3
    return s.current_agenda_index + 1


def _check_possession_kill(controller, inv, card_id: str) -> None:
    """Possession: horror > twice sanity -> immediately eliminated and killed.

    Simplification: elimination goes through the normal defeat pipeline by
    clamping horror to sanity; the 'killed' campaign flag is recorded in
    scenario.vars["killed_investigators"] for the campaign layer.
    """
    game = controller.game
    if inv.horror > 2 * inv.sanity:
        inv.horror = inv.sanity
        killed = game.state.scenario.vars.setdefault("killed_investigators", [])
        if inv.investigator_id not in killed:
            killed.append(inv.investigator_id)
        controller.log(f"💀 【{game.state.card_name(card_id)}】：恐惧超过神智两倍，立即退场（被杀）")
        game.damage_engine._check_defeat(inv.investigator_id)


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

def resolve_carcosa_treachery(controller, card_id: str, *, investigator_id: str,
                              choice: str | None = None) -> dict | None:
    """Resolve a Path to Carcosa treachery. Returns result dict, or None."""
    game = controller.game
    inv = game.state.get_investigator(investigator_id)
    if inv is None:
        return None
    log = controller.log
    run_test = controller._run_skill_test
    svars = game.state.scenario.vars

    # ---- The Last King ----
    if card_id == "fine_dining":
        bystanders = [iid for iid, inst in game.state.cards_in_play.items()
                      if "bystander" in _tags_of(game, iid)]
        if choice is None and inv.clues > 0 and bystanders:
            svars["pending_choice"] = {
                "card_id": card_id,
                "investigator_id": investigator_id,
                "prompt": "正式晚餐：选择 放置1线索到旁人支援 或 受1恐惧+1伤害",
                "options": [
                    {"id": "place_clue", "label": "放置1个你的线索到旁人支援上"},
                    {"id": "take_damage", "label": "受到1恐惧和1伤害"},
                ],
            }
            return {"pending": True, "message": "pending_choice"}
        if choice == "place_clue" and inv.clues > 0 and bystanders:
            inv.clues -= 1
            inst = game.state.get_card_instance(bystanders[0])
            inst.uses["clues"] = inst.uses.get("clues", 0) + 1
            log(f"🍽️ 遭遇：正式晚餐——放置1线索到【{game.state.card_name(inst.card_id)}】")
        else:
            # 无线索/无旁人资产时只能受伤（官方必须二选一，此处无可执行项）
            game.damage_engine.deal_damage(investigator_id, damage=1, horror=1)
            log("🍽️ 遭遇：正式晚餐——受到1恐惧和1伤害")
        return {"pending": False, "message": "fine_dining"}

    if card_id == "tough_crowd":
        # 简化：谈判+1行动未强制（引擎无谈判动作）；本轮结束自动弃掉
        svars["tough_crowd"] = True
        _register_round_end_flag(game, "tough_crowd")
        log("😾 遭遇：难缠的客人——放在密谋旁（本轮谈判+1行动[未强制]，轮末弃掉）")
        return {"pending": False, "message": "tough_crowd"}

    # ---- Delusions（Hidden 低语）----
    if card_id in _WHISPERS_RESTRICTION:
        # 简化：数字版无法保密——直接加入手牌；持续限制记入 vars，未强制
        inv.hand.append(card_id)
        svars.setdefault("whispers_in_your_head", {})[investigator_id] = card_id
        log(f"🤫 遭遇：脑海中的低语——加入手牌（{_WHISPERS_RESTRICTION[card_id]}，限制未强制；"
            f"可用 activate_discard_whispers 花2行动弃掉）")
        return {"pending": False, "message": card_id}

    if card_id == "descent_into_madness":
        if inv.horror >= 3 and inv.actions_remaining > 0:
            inv.actions_remaining -= 1
            log("📉 遭遇：深陷疯狂——恐惧≥3，失去1行动，涌动")
        else:
            log("📉 遭遇：深陷疯狂——涌动")
        return {"pending": False, "message": "surge", "surge": True}

    # ---- Byakhee ----
    if card_id == "hunted_by_byakhee":
        log("🦅 遭遇：拜亚基的猎杀（敏捷6，失败翻开遭遇堆顶X张）")

        def on_fail(r):
            x = min(_margin_fail(r), len(game.state.scenario.encounter_deck))
            if x <= 0:
                return
            deck = game.state.scenario.encounter_deck
            revealed = [deck.pop(0) for _ in range(x)]
            byakhee = [c for c in revealed if _is_enemy_with_tag(game, c, "byakhee")]
            omens = [c for c in revealed
                     if (game.state.get_card_data(c) is not None
                         and game.state.get_card_data(c).type.value == "treachery"
                         and "omen" in (game.state.get_card_data(c).traits or []))]
            if byakhee:
                chosen = byakhee[0]
                revealed.remove(chosen)
                controller._spawn_enemy_from_encounter(chosen, investigator_id)
                log(f"  → 抽到【{game.state.card_name(chosen)}】并与你交战")
            if omens:
                game.damage_engine.deal_damage(investigator_id, horror=1)
                log("  → 翻开征兆诡计：受1恐惧")
            # 未抽取的翻开示卡放回并混洗遭遇牌堆
            deck.extend(revealed)
            random.shuffle(deck)
        run_test(investigator_id, skill=Skill.AGILITY, difficulty=6, on_failure=on_fail)
        return {"pending": False, "message": "hunted_by_byakhee"}

    # ---- Evil Portents ----
    if card_id == "black_stars_rise_a":
        log("🌟 遭遇：黑星升起（智力4，失败：密谋+1毁灭 或 按差额受恐惧）")

        def on_fail(r):
            # 简化：自动选择按差额受恐惧（避免自动推进密谋的二选一）
            m = _margin_fail(r)
            if m:
                game.damage_engine.deal_damage(investigator_id, horror=m)
        run_test(investigator_id, skill=Skill.INTELLECT, difficulty=4, on_failure=on_fail)
        return {"pending": False, "message": "black_stars_rise_a"}

    if card_id == "spires_of_carcosa":
        controller.attach_card_to_location("spires_of_carcosa", inv.location_id)
        loc = game.state.get_location(inv.location_id)
        if loc is not None:
            loc.doom += 2
        controller._check_agenda_threshold()
        log("🏰 遭遇：卡尔克萨尖柱——叠加到所在地点并+2毁灭"
            "（可用 activate_spires_investigate 调查移除毁灭）")
        return {"pending": False, "message": "spires_of_carcosa"}

    if card_id == "twisted_to_his_will":
        x = game.state.total_doom_in_play()
        if x <= 0:
            log("😈 遭遇：邪念扭曲——场上无毁灭，涌动")
            return {"pending": False, "message": "surge", "surge": True}
        log(f"😈 遭遇：邪念扭曲（意志{x}，失败随机弃2手牌）")

        def on_fail(r):
            for cid in random.sample(inv.hand, min(2, len(inv.hand))):
                inv.hand.remove(cid)
                inv.discard.append(cid)
                log(f"  → 随机弃掉【{game.state.card_name(cid)}】")
        run_test(investigator_id, skill=Skill.WILLPOWER, difficulty=x, on_failure=on_fail)
        return {"pending": False, "message": "twisted_to_his_will"}

    # ---- Hauntings ----
    if card_id == "spirits_torment":
        controller.attach_card_to_location("spirits_torment", inv.location_id)
        attached_loc = inv.location_id

        holder: list[Any] = []

        def _on_move(ctx):
            if controller.location_attachment_instance(attached_loc, "spirits_torment") is None:
                # 卡已离场（被 activate_spirits_torment 弃掉）→ 自注销
                game.event_bus.unregister(holder[0])
                return
            moving = game.state.get_investigator(ctx.investigator_id)
            if moving is None or moving.location_id != attached_loc:
                return
            if ctx.location_id == attached_loc:
                return
            # 简化：自动选择受1恐惧（官方为 1恐惧 或 失去1行动 二选一）
            game.damage_engine.deal_damage(ctx.investigator_id, horror=1)
            log(f"👻 恶灵作祟：【{ctx.investigator_id}】离开被叠加地点，受1恐惧")

        holder.append(game.event_bus.register(GameEvent.MOVE_ACTION_INITIATED, _on_move,
                                              priority=TimingPriority.AFTER))
        log("👻 遭遇：恶灵作祟——叠加到所在地点（离开者受1恐惧；"
            "可用 activate_spirits_torment 放1线索弃掉）")
        return {"pending": False, "message": "spirits_torment"}

    # ---- Hastur's Gift ----
    if card_id == "dance_of_the_yellow_king":
        possessed = _enemies_with_tag(game, "possessed")
        if not possessed:
            log("💃 遭遇：黄衣之王之舞——无附身敌人，涌动")
            return {"pending": False, "message": "surge", "surge": True}
        log("💃 遭遇：黄衣之王之舞（意志3，失败最近附身敌人交战并立即攻击）")

        def on_fail(r):
            target = controller._nearest_enemy_with(inv, "possessed") or possessed[0]
            inst = game.state.get_card_instance(target)
            if inst is not None:
                inst.exhausted = False
            # 简化：直接移至调查员地点交战（官方逐地点移动，结果相同）
            _engage_investigator(game, target, inv)
            _enemy_attack(game, target, investigator_id)
            log(f"  → 【{game.state.card_name(game.state.get_card_instance(target).card_id)}】就绪、交战并立即攻击")
        run_test(investigator_id, skill=Skill.WILLPOWER, difficulty=3, on_failure=on_fail)
        return {"pending": False, "message": "dance_of_the_yellow_king"}

    # ---- Cult of the Yellow Sign ----
    if card_id == "the_kings_edict":
        moved = 0
        for iid in _enemies_with_tag(game, "cultist"):
            loc_id = _enemy_location(game, iid)
            loc = game.state.get_location(loc_id) if loc_id else None
            if loc is not None and loc.clues > 0:
                loc.clues -= 1
                inst = game.state.get_card_instance(iid)
                inst.uses["clues"] = inst.uses.get("clues", 0) + 1
                moved += 1
        if moved == 0:
            log("📜 遭遇：王之法令——未移动任何线索，涌动")
            return {"pending": False, "message": "surge", "surge": True}
        # 简化：本轮异教徒每线索/毁灭+1战斗——记入 vars，未强制（无战斗值修正钩子）
        svars["kings_edict_round"] = game.state.scenario.round_number
        log(f"📜 遭遇：王之法令——{moved} 个线索移到异教徒敌人上（本轮+1战斗/每线索毁灭[未强制]）")
        return {"pending": False, "message": "the_kings_edict"}

    # ---- Decay ----
    if card_id == "ooze_and_filth":
        # 简化：每地点+1隐蔽未强制（location_shroud_bonus 为硬编码白名单，引擎缺口）；
        # 本轮结束自动弃掉
        svars["ooze_and_filth"] = True
        _register_round_end_flag(game, "ooze_and_filth")
        log("🤢 遭遇：淤泥与污物——放在场景旁（本轮每地点+1隐蔽[未强制]，轮末弃掉）")
        return {"pending": False, "message": "ooze_and_filth"}

    if card_id == "corrosion":
        x = _shroud_of(controller, inv.location_id)
        discarded = _auto_discard_assets(controller, inv, x, item_only=True)
        if not discarded:
            log("🧪 遭遇：锈蚀——未弃掉任何道具支援，涌动")
            return {"pending": False, "message": "surge", "surge": True}
        log(f"🧪 遭遇：锈蚀——弃掉道具支援【{_log_names(game, discarded)}】（费用合计≥{x}）")
        return {"pending": False, "message": "corrosion"}

    # ---- Stranger ----
    if card_id == "marked_by_the_sign":
        mitpm = _pallid_mask_in_play(game)
        difficulty = 4 if mitpm else 2
        log(f"🎭 遭遇：印记之痕（意志{difficulty}，失败受2恐惧"
            + ("，视为直接恐惧" if mitpm else "") + "）")

        def on_fail(r):
            game.damage_engine.deal_damage(investigator_id, horror=2, direct=bool(mitpm))
        run_test(investigator_id, skill=Skill.WILLPOWER, difficulty=difficulty, on_failure=on_fail)
        return {"pending": False, "message": "marked_by_the_sign"}

    if card_id == "the_pale_mask_beckons":
        mitpm = _pallid_mask_in_play(game)
        if mitpm:
            for inv_id in list(game.state.player_order):
                target = game.state.get_investigator(inv_id)
                if target is None or target.is_defeated:
                    continue
                _enemy_attack(game, mitpm, inv_id)
            log("🎭 遭遇：苍白面具的呼唤——苍白面具下的男子攻击每位调查员")
            return {"pending": False, "message": "the_pale_mask_beckons"}
        # 简化：未实现承受者（bearer）追踪——搜索所有调查员的牌堆与弃牌堆
        found = None
        for inv_id in list(game.state.player_order):
            other = game.state.get_investigator(inv_id)
            if other is None:
                continue
            for pile in (other.deck, other.discard):
                if "the_man_in_the_pallid_mask" in pile:
                    pile.remove("the_man_in_the_pallid_mask")
                    found = other
                    break
            if found is not None:
                break
        if found is not None:
            random.shuffle(found.deck)
            controller._spawn_enemy_from_encounter("the_man_in_the_pallid_mask", investigator_id)
            log("🎭 遭遇：苍白面具的呼唤——从承受者牌堆中找出苍白面具下的男子并抽取")
        else:
            log("🎭 遭遇：苍白面具的呼唤——未找到苍白面具下的男子，无效果")
        return {"pending": False, "message": "the_pale_mask_beckons"}

    # ---- Echoes of the Past ----
    if card_id == "led_astray":
        cultists = _enemies_with_tag(game, "cultist")
        if choice is None and inv.clues > 0 and cultists:
            svars["pending_choice"] = {
                "card_id": card_id,
                "investigator_id": investigator_id,
                "prompt": "引入歧途：你必须决定——放置1线索到异教徒敌人 或 密谋+1毁灭",
                "options": [
                    {"id": "place_clue", "label": "放置1个你的线索到异教徒敌人上"},
                    {"id": "place_doom", "label": "当前密谋+1毁灭（可能推进）"},
                ],
            }
            return {"pending": True, "message": "pending_choice"}
        if choice == "place_clue" and inv.clues > 0 and cultists:
            inv.clues -= 1
            inst = game.state.get_card_instance(cultists[0])
            inst.uses["clues"] = inst.uses.get("clues", 0) + 1
            log(f"🌀 遭遇：引入歧途——放置1线索到【{game.state.card_name(inst.card_id)}】")
        else:
            # 无线索/无异教徒时只能放毁灭（官方必须二选一，此处无可执行项）
            game.state.scenario.doom_on_agenda += 1
            controller._check_agenda_threshold()
            log("🌀 遭遇：引入歧途——当前密谋+1毁灭")
        return {"pending": False, "message": "led_astray"}

    if card_id == "the_cults_search":
        doomed = [iid for iid in _enemies_with_tag(game, "cultist")
                  if (game.state.get_card_instance(iid).doom or 0) > 0]
        if doomed:
            total = 0
            for iid in doomed:
                inst = game.state.get_card_instance(iid)
                total += inst.doom
                inst.doom = 0
            game.state.scenario.doom_on_agenda += total
            controller._check_agenda_threshold()
            log(f"🔍 遭遇：邪教的搜查——{total} 点毁灭从异教徒移到当前密谋")
        else:
            pulled = _pull_enemy_from_encounter(game, "cultist")
            if pulled:
                controller._spawn_enemy_from_encounter(pulled, investigator_id)
                random.shuffle(game.state.scenario.encounter_deck)
                log(f"🔍 遭遇：邪教的搜查——抽到【{game.state.card_name(pulled)}】")
            else:
                log("🔍 遭遇：邪教的搜查——遭遇牌堆/弃牌堆中无异教徒敌人")
        return {"pending": False, "message": "the_cults_search"}

    # ---- The Unspeakable Oath ----
    if card_id == "straitjacket":
        if _threat_copy(game, inv, "straitjacket") is not None:
            log("🧥 遭遇：约束衣——威胁区已有约束衣，无效果")
            return {"pending": False, "message": "straitjacket"}
        _place_in_threat(game, inv, "straitjacket")
        # 占 1 服装槽 + 2 手槽：这些槽位中的支援返回手牌
        returned = []
        hands_freed = 0
        for iid in list(inv.play_area):
            inst = game.state.get_card_instance(iid)
            if inst is None:
                continue
            slots = list(getattr(inst, "slot_used", None) or [])
            if SlotType.BODY in slots or (SlotType.HAND in slots and hands_freed < 2):
                if SlotType.HAND in slots and SlotType.BODY not in slots:
                    hands_freed += 1
                game.state.cards_in_play.pop(iid, None)
                inv.play_area.remove(iid)
                inv.hand.append(inst.card_id)
                mgr = getattr(game.state, "slot_managers", {}).get(inv.investigator_id)
                if mgr is not None:
                    mgr.vacate(iid)
                returned.append(inst.card_id)
        # 简化：约束衣本身的槽位占用未接入 slot manager（未强制）；
        # 只能通过 activate_discard_straitjacket（2行动）离场
        svars.setdefault("straitjacket", {})[investigator_id] = True
        msg = f"，【{_log_names(game, returned)}】返回手牌" if returned else ""
        log(f"🧥 遭遇：约束衣——放入威胁区（占1服装槽+2手槽[占用未强制]{msg}）")
        return {"pending": False, "message": "straitjacket"}

    if card_id in ("gift_of_madness_a", "gift_of_madness_b"):
        # 简化：数字版无法保密——直接加入手牌；持续限制记入 vars，未强制
        # a=不能攻击附身敌人；b=不能触发地点上的[行动]能力
        inv.hand.append(card_id)
        svars.setdefault("gift_of_madness", {})[investigator_id] = card_id
        log("🎁 遭遇：疯狂礼物——加入手牌（持续限制未强制；"
            "可用 activate_gift_of_madness 花1行动将搁置怪物置于剧本牌堆下并弃掉）")
        return {"pending": False, "message": card_id}

    if card_id == "walls_closing_in":
        x = _shroud_of(controller, inv.location_id)
        log(f"🧱 遭遇：危墙迫近（意志{x}，失败：搁置怪物置于剧本牌堆下 或 按差额受恐惧）")

        def on_fail(r):
            # 简化：自动优先选择搁置怪物置于剧本牌堆下（官方二选一）
            if controller._set_aside_monster_under_scenario():
                log("  → 1个搁置怪物被置于剧本牌堆下")
            else:
                m = _margin_fail(r)
                if m:
                    game.damage_engine.deal_damage(investigator_id, horror=m)
        run_test(investigator_id, skill=Skill.WILLPOWER, difficulty=x, on_failure=on_fail)
        return {"pending": False, "message": "walls_closing_in"}

    # ---- A Phantom of Truth ----
    if card_id == "twin_suns":
        log("🌞 遭遇：双生太阳（智力4，失败：密谋-1毁灭 或 按差额受恐惧）")

        def on_fail(r):
            # 简化：自动优先选择移除1毁灭（严格有利；官方二选一）
            if game.state.scenario.doom_on_agenda > 0:
                game.state.scenario.doom_on_agenda -= 1
                log("  → 当前密谋-1毁灭")
            else:
                m = _margin_fail(r)
                if m:
                    game.damage_engine.deal_damage(investigator_id, horror=m)
        run_test(investigator_id, skill=Skill.INTELLECT, difficulty=4, on_failure=on_fail)
        return {"pending": False, "message": "twin_suns"}

    if card_id == "deadly_fate":
        log("☠️ 遭遇：致命运数（意志3，失败弃遭遇堆顶直到敌人并抽取）")

        def on_fail(r):
            s = game.state.scenario
            found = None
            while s.encounter_deck:
                cid = s.encounter_deck.pop(0)
                cd = game.state.get_card_data(cid)
                if cd is not None and cd.type.value == "enemy":
                    found = cid
                    break
                s.encounter_discard.append(cid)
            if found is None:
                game.damage_engine.deal_damage(investigator_id, horror=1)
                log("  → 未翻到敌人，受1恐惧")
                return
            # 简化：自动选择抽取该敌人（官方可选让其从弃牌堆攻击你）
            controller._spawn_enemy_from_encounter(found, investigator_id)
            log(f"  → 抽到【{game.state.card_name(found)}】并与你交战")
        run_test(investigator_id, skill=Skill.WILLPOWER, difficulty=3, on_failure=on_fail)
        return {"pending": False, "message": "deadly_fate"}

    if card_id == "torturous_chords":
        log("🎵 遭遇：折磨和弦（意志5，失败放入威胁区并按差额放资源）")

        def on_fail(r):
            m = _margin_fail(r)
            if m <= 0:
                return
            _place_in_threat(game, inv, "torturous_chords")
            svars.setdefault("torturous_chords", {})[investigator_id] = m
            # 简化：打出卡牌+1费用并移除其上资源未强制（无费用修正钩子，引擎缺口）
            log(f"  → 放入威胁区，上有{m}资源（打出卡+1费[未强制]）")
        run_test(investigator_id, skill=Skill.WILLPOWER, difficulty=5, on_failure=on_fail)
        return {"pending": False, "message": "torturous_chords"}

    # frozen_in_fear 由核心分支处理（resolve_encounter_card 中既有逻辑）。

    if card_id == "lost_soul":
        doubt = int(svars.get("doubt", 0) or 0)
        conviction = int(svars.get("conviction", 0) or 0)
        if doubt >= conviction:
            skill, cross = Skill.INTELLECT, Skill.WILLPOWER
        else:
            skill, cross = Skill.WILLPOWER, Skill.INTELLECT
        x = inv.get_skill(cross)
        log(f"👻 遭遇：失魂落魄（疑惑{doubt}/确信{conviction}，"
            f"{'智力' if skill == Skill.INTELLECT else '意志'}检定{x}，失败受2伤害）")
        run_test(investigator_id, skill=skill, difficulty=x,
                 on_failure=lambda r: game.damage_engine.deal_damage(investigator_id, damage=2))
        return {"pending": False, "message": "lost_soul"}

    # ---- The Pallid Mask ----
    if card_id == "eyes_in_the_walls":
        log("👀 遭遇：墙中之眼（意志3，失败按差额受恐惧）")
        # 简化：恐惧尽量均分到可分配卡——走伤害引擎默认分配，均分规则未强制
        run_test(investigator_id, skill=Skill.WILLPOWER, difficulty=3,
                 on_failure=lambda r: game.damage_engine.deal_damage(
                     investigator_id, horror=_margin_fail(r)))
        return {"pending": False, "message": "eyes_in_the_walls"}

    if card_id == "the_shadow_behind_you":
        if _threat_copy(game, inv, "the_shadow_behind_you") is not None:
            log("🌑 遭遇：身后暗影——威胁区已有（限1），无效果")
            return {"pending": False, "message": "the_shadow_behind_you"}
        _place_in_threat(game, inv, "the_shadow_behind_you")
        svars.setdefault("shadow_behind_you", {})[investigator_id] = {"looked": False}

        holder: list[Any] = []

        def _on_turn_end(ctx):
            if ctx.investigator_id != investigator_id:
                # 多人：只在属主的回合结束时结算，不提前注销
                return
            game.event_bus.unregister(holder[0])
            rec = svars.get("shadow_behind_you", {}).pop(investigator_id, None)
            if rec is None:
                return
            iid = _threat_copy(game, inv, "the_shadow_behind_you")
            if iid is not None:
                _remove_from_threat(game, inv, iid)
            game.state.scenario.encounter_discard.append("the_shadow_behind_you")
            if rec.get("looked"):
                log("🌑 身后暗影：你已查看身后，弃掉身后暗影")
                return
            # 简化：自动选择弃资源（有资源时），否则弃手牌（官方二选一）
            if inv.resources > 0:
                inv.resources = 0
                log("🌑 身后暗影：未查看身后，弃掉所有资源")
            else:
                for cid in list(inv.hand):
                    inv.hand.remove(cid)
                    inv.discard.append(cid)
                log("🌑 身后暗影：未查看身后，弃掉所有手牌")

        holder.append(game.event_bus.register(GameEvent.INVESTIGATOR_TURN_ENDS,
                                              _on_turn_end,
                                              priority=TimingPriority.AFTER))
        log("🌑 遭遇：身后暗影——放入威胁区（回合结束未查看：弃全部资源或手牌；"
            "可用 activate_look_behind 查看）")
        return {"pending": False, "message": "the_shadow_behind_you"}

    if card_id == "the_pit_below":
        if controller.location_attachment_instance(inv.location_id, "the_pit_below"):
            log("🕳️ 遭遇：地下深坑——所在地点已有，弃掉并涌动")
            return {"pending": False, "message": "surge", "surge": True}
        iid = controller.attach_card_to_location("the_pit_below", inv.location_id)
        attached_loc = inv.location_id
        # 简化：+1隐蔽未强制（location_shroud_bonus 硬编码白名单，引擎缺口）

        def _on_round_end(_ctx):
            for other_id in list(game.state.player_order):
                other = game.state.get_investigator(other_id)
                if other is not None and other.location_id == attached_loc \
                        and not other.is_defeated:
                    game.damage_engine.deal_damage(other_id, damage=3)
            controller.detach_card_from_location(iid)
            log("🕳️ 地下深坑：本轮结束——被叠加地点的调查员各受3伤害，弃掉地下深坑")

        _register_one_shot(game, GameEvent.ROUND_ENDS, _on_round_end)
        log("🕳️ 遭遇：地下深坑——叠加到所在地点（+1隐蔽[未强制]；轮末该地点每人受3伤害）")
        return {"pending": False, "message": "the_pit_below"}

    # ---- Black Stars Rise ----
    if card_id == "crashing_floods":
        level = _agenda_act_level(game)
        log(f"🌊 遭遇：洪水肆虐（敏捷3，失败受{level}伤害并失去{level}行动）")

        def on_fail(r):
            game.damage_engine.deal_damage(investigator_id, damage=level)
            lost = min(level, inv.actions_remaining)
            inv.actions_remaining -= lost
        run_test(investigator_id, skill=Skill.AGILITY, difficulty=3, on_failure=on_fail)
        return {"pending": False, "message": "crashing_floods"}

    if card_id == "worlds_merge":
        level = _agenda_act_level(game)
        log(f"🌍 遭遇：世界融合（意志3，失败受{level}恐惧并弃{level}手牌）")

        def on_fail(r):
            game.damage_engine.deal_damage(investigator_id, horror=level)
            # 简化：自动弃前N张（官方由你选择）
            for cid in list(inv.hand)[:level]:
                inv.hand.remove(cid)
                inv.discard.append(cid)
        run_test(investigator_id, skill=Skill.WILLPOWER, difficulty=3, on_failure=on_fail)
        return {"pending": False, "message": "worlds_merge"}

    # ---- Dim Carcosa ----
    if card_id == "dismal_curse":
        difficulty = 3 + (2 if inv.remaining_sanity <= 0 else 0)
        log(f"🌫️ 遭遇：阴郁诅咒（意志{difficulty}，失败受2伤害）")

        def on_fail(r):
            dmg = 4 if inv.horror > 2 * inv.sanity else 2
            game.damage_engine.deal_damage(investigator_id, damage=dmg)
        run_test(investigator_id, skill=Skill.WILLPOWER, difficulty=difficulty, on_failure=on_fail)
        return {"pending": False, "message": "dismal_curse"}

    if card_id == "realm_of_madness":
        x = inv.horror
        discarded = _auto_discard_assets(controller, inv, x, item_only=False)
        if not discarded and x > 0:
            game.damage_engine.deal_damage(investigator_id, horror=2)
            log(f"😵 遭遇：疯狂领域——未弃掉任何卡牌（需费用≥{x}），受2恐惧")
        else:
            log(f"😵 遭遇：疯狂领域——弃掉【{_log_names(game, discarded)}】（费用合计≥{x}）")
        return {"pending": False, "message": "realm_of_madness"}

    if card_id == "the_final_act":
        if inv.remaining_sanity <= 0:
            game.state.scenario.doom_on_agenda += 2
            controller._check_agenda_threshold()
            log("🎬 遭遇：最后一幕——无剩余神智，当前密谋+2毁灭，涌动")
        else:
            log("🎬 遭遇：最后一幕——涌动")
        return {"pending": False, "message": "surge", "surge": True}

    if card_id in ("possession_a", "possession_b", "possession_c"):
        # 简化：数字版无法保密——直接加入手牌
        # a 的"可投入同地点检定使其自动失败"未强制（无投入拦截钩子）
        inv.hand.append(card_id)
        svars.setdefault("possession", {})[investigator_id] = card_id
        log(f"😈 遭遇：恶灵附身——加入手牌（{card_id[-1]}）")
        _check_possession_kill(controller, inv, card_id)
        return {"pending": False, "message": card_id}

    return None


# ---------------------------------------------------------------------------
# 公开激活方法（Hidden/持续卡的 [行动] 能力；供 session 层/测试调用）
# ---------------------------------------------------------------------------

def activate_discard_whispers(controller, investigator_id: str) -> bool:
    """[行动][行动]：弃掉手牌中的脑海中的低语。"""
    game = controller.game
    inv = game.state.get_investigator(investigator_id)
    if inv is None or inv.actions_remaining < 2:
        return False
    card_id = game.state.scenario.vars.get("whispers_in_your_head", {}).get(investigator_id)
    if card_id is None or card_id not in inv.hand:
        return False
    inv.actions_remaining -= 2
    inv.hand.remove(card_id)
    inv.discard.append(card_id)
    game.state.scenario.vars.get("whispers_in_your_head", {}).pop(investigator_id, None)
    controller.log(f"🤫 花2行动弃掉【{game.state.card_name(card_id)}】")
    return True


def activate_gift_of_madness(controller, investigator_id: str) -> bool:
    """[行动]：随机将1个搁置的怪物敌人置于剧本牌堆下，弃掉手牌中的疯狂礼物。"""
    game = controller.game
    inv = game.state.get_investigator(investigator_id)
    if inv is None or inv.actions_remaining < 1:
        return False
    card_id = game.state.scenario.vars.get("gift_of_madness", {}).get(investigator_id)
    if card_id is None or card_id not in inv.hand:
        return False
    monsters = game.state.scenario.vars.get("set_aside_monsters") or []
    if not monsters:
        return False
    inv.actions_remaining -= 1
    chosen = random.choice(monsters)
    monsters.remove(chosen)
    game.state.scenario.vars.setdefault("under_scenario_deck", []).append(chosen)
    inv.hand.remove(card_id)
    inv.discard.append(card_id)
    game.state.scenario.vars.get("gift_of_madness", {}).pop(investigator_id, None)
    controller.log(f"🎁 花1行动：【{game.state.card_name(chosen)}】置于剧本牌堆下，弃掉疯狂礼物")
    return True


def activate_discard_possession(controller, investigator_id: str,
                                target_id: str | None = None) -> bool:
    """[行动]：弃掉手牌中的恶灵附身（b=花5资源；c=对同地点1调查员造成2伤害）。"""
    game = controller.game
    inv = game.state.get_investigator(investigator_id)
    if inv is None or inv.actions_remaining < 1:
        return False
    card_id = game.state.scenario.vars.get("possession", {}).get(investigator_id)
    if card_id not in ("possession_b", "possession_c") or card_id not in inv.hand:
        return False
    if card_id == "possession_b":
        if inv.resources < 5:
            return False
        inv.resources -= 5
    else:
        # possession_c：默认对自己（简化：同地点目标由 target_id 指定）
        victim = game.state.get_investigator(target_id) if target_id else inv
        if victim is None or victim.location_id != inv.location_id:
            return False
        game.damage_engine.deal_damage(victim.investigator_id, damage=2)
    inv.actions_remaining -= 1
    inv.hand.remove(card_id)
    inv.discard.append(card_id)
    game.state.scenario.vars.get("possession", {}).pop(investigator_id, None)
    controller.log(f"😈 花1行动弃掉【{game.state.card_name(card_id)}】")
    return True


def activate_discard_straitjacket(controller, investigator_id: str) -> bool:
    """[行动][行动]：弃掉威胁区中的约束衣。"""
    game = controller.game
    inv = game.state.get_investigator(investigator_id)
    if inv is None or inv.actions_remaining < 2:
        return False
    iid = _threat_copy(game, inv, "straitjacket")
    if iid is None:
        return False
    inv.actions_remaining -= 2
    _remove_from_threat(game, inv, iid)
    game.state.scenario.encounter_discard.append("straitjacket")
    game.state.scenario.vars.get("straitjacket", {}).pop(investigator_id, None)
    controller.log("🧥 花2行动弃掉【约束衣】")
    return True


def activate_look_behind(controller, investigator_id: str) -> bool:
    """[行动]：查看你身后（身后暗影）。"""
    game = controller.game
    inv = game.state.get_investigator(investigator_id)
    if inv is None or inv.actions_remaining < 1:
        return False
    rec = game.state.scenario.vars.get("shadow_behind_you", {}).get(investigator_id)
    if rec is None:
        return False
    inv.actions_remaining -= 1
    rec["looked"] = True
    controller.log("🌑 你查看了身后")
    return True


def activate_spirits_torment(controller, investigator_id: str) -> bool:
    """[行动]：将你的1个线索放到恶灵作祟被叠加的地点上，弃掉恶灵作祟。"""
    game = controller.game
    inv = game.state.get_investigator(investigator_id)
    if inv is None or inv.actions_remaining < 1 or inv.clues < 1:
        return False
    loc_id = controller.location_with_attachment("spirits_torment")
    if loc_id is None:
        return False
    loc = game.state.get_location(loc_id)
    iid = controller.location_attachment_instance(loc_id, "spirits_torment")
    inv.actions_remaining -= 1
    inv.clues -= 1
    loc.clues += 1
    controller.detach_card_from_location(iid)
    controller.log("👻 花1行动：放置1线索，弃掉【恶灵作祟】")
    return True


def activate_spires_investigate(controller, investigator_id: str) -> bool:
    """[行动]：调查。若成功，不发现线索，改为移除卡尔克萨尖柱上1毁灭。

    毁灭全数移除后按卡面弃掉卡尔克萨尖柱（"若无毁灭则弃掉"）。
    """
    game = controller.game
    inv = game.state.get_investigator(investigator_id)
    if inv is None or inv.actions_remaining < 1:
        return False
    iid = controller.location_attachment_instance(inv.location_id, "spires_of_carcosa")
    if iid is None:
        return False
    loc = game.state.get_location(inv.location_id)
    inv.actions_remaining -= 1
    difficulty = _shroud_of(controller, inv.location_id)

    def _ok(_r):
        loc.doom = max(0, loc.doom - 1)
        controller.log("🏰 调查成功：移除卡尔克萨尖柱上1毁灭")
        if loc.doom <= 0:
            controller.detach_card_from_location(iid)
            controller.log("🏰 卡尔克萨尖柱上无毁灭，弃掉")

    # _run_skill_test 不暴露成功回调，直接调用检定引擎
    game.skill_test_engine.run_test(
        investigator_id=investigator_id,
        skill_type=Skill.INTELLECT,
        difficulty=difficulty,
        committed_card_ids=[],
        on_success=_ok,
        on_failure=lambda r: None,
    )
    return True
