"""Dunwich Legacy encounter treachery resolution.

Called from ScenarioController.resolve_encounter_card as a fallback before the
(未实现) branch. Each handler returns {"pending": bool, "message": str} or None
(to continue to the next matcher).

Simplifications (documented per card): scenario-specific entities (Spawn of
Yog-Sothoth, Hunting Horror, Sentinel Hill, Dreamlands) use simplified logic
when the full scenario framework isn't present.
"""

from __future__ import annotations

import random
from typing import Any

from backend.models.enums import ChaosTokenType, Skill

# 标记类别
_SYMBOL_TOKENS = {
    ChaosTokenType.SKULL, ChaosTokenType.CULTIST,
    ChaosTokenType.TABLET, ChaosTokenType.ELDER_THING,
    ChaosTokenType.AUTO_FAIL,
}


def _margin_fail(result) -> int:
    return max(0, (result.difficulty or 0) - (result.modified_skill or 0))


def _discard_top(game, inv, n: int) -> list[str]:
    discarded = []
    for _ in range(n):
        if inv.deck:
            cid = inv.deck.pop(0)
            inv.discard.append(cid)
            discarded.append(cid)
    return discarded


def _enemies_in_play(game, keyword: str) -> list[str]:
    out = []
    for iid, inst in game.state.cards_in_play.items():
        cd = game.state.get_card_data(inst.card_id)
        if cd is None or cd.type.value != "enemy":
            continue
        kws = list(getattr(cd, "keywords", None) or []) + list(getattr(cd, "traits", None) or [])
        if keyword in kws:
            out.append(iid)
    return out


def _log_names(game, cids: list[str]) -> str:
    return "、".join(game.state.card_name(c) for c in cids)


def resolve_dunwich_treachery(controller, card_id: str, *, investigator_id: str) -> dict | None:
    """Resolve a Dunwich treachery. Returns result dict, or None if unhandled."""
    game = controller.game
    inv = game.state.get_investigator(investigator_id)
    if inv is None:
        return None
    log = controller.log
    run_test = controller._run_skill_test

    # ---- 简单弃牌/伤害类 ----
    if card_id == "across_space_and_time":
        discarded = _discard_top(game, inv, 3)
        log(f"🌌 遭遇：跨越时空——弃掉牌堆顶3张【{_log_names(game, discarded)}】")
        return {"pending": False, "message": "across_space_and_time"}

    if card_id == "visions_of_futures_past":
        log("🔮 遭遇：穿越时间的幻觉（意志5，失败按差额弃牌堆顶）")
        run_test(investigator_id, skill=Skill.WILLPOWER, difficulty=5,
                 on_failure=lambda r: _discard_top(game, inv, _margin_fail(r)))
        return {"pending": False, "message": "visions_of_futures_past"}

    if card_id == "ephemeral_exhibits":
        log("🖼️ 遭遇：短暂的展览（智力3，失败按差额失去行动）")

        def on_fail(r):
            lost = min(_margin_fail(r), inv.actions_remaining)
            inv.actions_remaining -= lost
            if lost:
                log(f"  → 失去 {lost} 个行动")
        run_test(investigator_id, skill=Skill.INTELLECT, difficulty=3, on_failure=on_fail)
        return {"pending": False, "message": "ephemeral_exhibits"}

    if card_id == "eager_for_death":
        difficulty = 2 + inv.damage
        log(f"👻 遭遇：渴望死亡（意志{difficulty}，失败受2恐惧）")
        run_test(investigator_id, skill=Skill.WILLPOWER, difficulty=difficulty,
                 on_failure=lambda r: game.damage_engine.deal_damage(investigator_id, horror=2))
        return {"pending": False, "message": "eager_for_death"}

    if card_id == "strange_signs":
        log("🪧 遭遇：怪异标记（智力3，失败地点+1线索）")

        def on_fail(r):
            loc = game.state.get_location(inv.location_id)
            if loc is not None:
                loc.clues += 1
        run_test(investigator_id, skill=Skill.INTELLECT, difficulty=3, on_failure=on_fail)
        return {"pending": False, "message": "strange_signs"}

    if card_id == "twist_of_fate":
        token = game.chaos_bag.draw()
        token_val = getattr(token, "value", str(token))
        if token == ChaosTokenType.ELDER_SIGN or token == ChaosTokenType.PLUS_1:
            log(f"🍀 遭遇：扭转命运——抽出[{token_val}]，无事发生")
        elif token in _SYMBOL_TOKENS:
            log(f"🍀 遭遇：扭转命运——抽出[{token_val}]，受到2恐惧")
            game.damage_engine.deal_damage(investigator_id, horror=2)
        else:
            log(f"🍀 遭遇：扭转命运——抽出[{token_val}]，受到1伤害")
            game.damage_engine.deal_damage(investigator_id, damage=1)
        return {"pending": False, "message": "twist_of_fate"}

    if card_id == "collapsing_reality":
        # 简化：当前无异次元地点机制，按"否则"处理
        log("💥 遭遇：现实崩塌——受到2伤害")
        game.damage_engine.deal_damage(investigator_id, damage=2)
        return {"pending": False, "message": "collapsing_reality"}

    if card_id == "broken_rails":
        if inv.actions_remaining > 0:
            inv.actions_remaining -= 1
        msg = "失去1行动"
        if inv.damage >= 4 and inv.play_area:
            iid = inv.play_area[0]
            inst = game.state.cards_in_play.pop(iid, None)
            if inst is not None:
                inv.play_area.remove(iid)
                inv.discard.append(inst.card_id)
                msg += f"，弃掉【{game.state.card_name(inst.card_id)}】"
        log(f"🛤️ 遭遇：铁轨断裂——{msg}")
        return {"pending": False, "message": "broken_rails"}

    if card_id == "something_in_the_drinks":
        if inv.actions_remaining > 0:
            inv.actions_remaining -= 1
        log("🍺 遭遇：酒里有毒——失去1行动，涌动")
        return {"pending": False, "message": "surge", "surge": True}

    if card_id == "arousing_suspicions":
        loc = game.state.get_location(inv.location_id)
        placed = 0
        if loc is not None:
            for iid in list(loc.enemies) + list(inv.threat_area):
                kws = _keywords_of(game, iid)
                if "罪犯" in kws or "criminal" in kws:
                    inst = game.state.get_card_instance(iid)
                    if inst is not None:
                        inst.doom += 1
                        placed += 1
        if placed == 0:
            inv.resources = max(0, inv.resources - 2)
            log("🚨 遭遇：引起怀疑——无罪犯敌人，失去2资源")
        else:
            log(f"🚨 遭遇：引起怀疑——{placed} 个罪犯敌人各+1毁灭")
            controller._check_agenda_threshold()
        return {"pending": False, "message": "arousing_suspicions"}

    if card_id == "rites_howled":
        discarded = _discard_top(game, inv, 3)
        log(f"📿 遭遇：哭号仪式——弃掉牌堆顶3张【{_log_names(game, discarded)}】")
        return {"pending": False, "message": "rites_howled"}

    if card_id == "vortex_of_time":
        log("🌀 遭遇：时间漩涡（意志4，失败受2伤害）")
        run_test(investigator_id, skill=Skill.WILLPOWER, difficulty=4,
                 on_failure=lambda r: game.damage_engine.deal_damage(investigator_id, damage=2))
        return {"pending": False, "message": "vortex_of_time"}

    if card_id == "claws_of_steam":
        log("🦾 遭遇：蒸气之爪（意志3，失败受2伤害且本轮不能离开）")

        def on_fail(r):
            game.damage_engine.deal_damage(investigator_id, damage=2)
            game.state.scenario.vars["claws_rooted"] = inv.location_id
        run_test(investigator_id, skill=Skill.WILLPOWER, difficulty=3, on_failure=on_fail)
        return {"pending": False, "message": "claws_of_steam"}

    if card_id == "passage_into_the_veil":
        log("🚪 遭遇：通往异界的道路（意志3，失败：弃牌堆顶5张 或 1直接伤害+盟友各1伤）")

        def on_fail(r):
            if len(inv.deck) >= 5:
                discarded = _discard_top(game, inv, 5)
                log(f"  → 弃掉牌堆顶5张【{_log_names(game, discarded)}】")
            else:
                game.damage_engine.deal_damage(investigator_id, damage=1, direct=True)
                for iid in inv.play_area:
                    inst = game.state.get_card_instance(iid)
                    if inst is not None:
                        inst.damage += 1
                log("  → 受到1直接伤害，盟友各受1伤害")
        run_test(investigator_id, skill=Skill.WILLPOWER, difficulty=3, on_failure=on_fail)
        return {"pending": False, "message": "passage_into_the_veil"}

    if card_id == "kidnapped":
        log("😱 遭遇：绑架！（意志4，失败失去1盟友或受2伤害）")

        def on_fail(r):
            allies = [iid for iid in inv.play_area
                      if "ally" in (game.state.get_card_data(
                          game.state.get_card_instance(iid).card_id).traits or [])
                      if game.state.get_card_instance(iid)
                      and game.state.get_card_data(game.state.get_card_instance(iid).card_id)]
            if allies:
                iid = allies[0]
                inst = game.state.cards_in_play.pop(iid, None)
                if inst is not None:
                    inv.play_area.remove(iid)
                    log(f"  → 【{game.state.card_name(inst.card_id)}】被绑架！")
            else:
                game.damage_engine.deal_damage(investigator_id, damage=2)
                log("  → 无盟友，受到2伤害")
        run_test(investigator_id, skill=Skill.WILLPOWER, difficulty=4, on_failure=on_fail)
        return {"pending": False, "message": "kidnapped"}

    if card_id == "pushed_into_the_beyond":
        if inv.play_area:
            iid = inv.play_area[0]
            inst = game.state.cards_in_play.pop(iid, None)
            if inst is not None:
                inv.play_area.remove(iid)
                inv.deck.append(inst.card_id)
                random.shuffle(inv.deck)
                chosen = inst.card_id
            else:
                chosen = None
        else:
            chosen = None
        discarded = _discard_top(game, inv, 3)
        msg = f"遭遇：异界放逐——【{game.state.card_name(chosen)}】洗回牌堆，弃牌堆顶3张" if chosen else "遭遇：异界放逐——弃牌堆顶3张"
        if chosen and chosen in discarded:
            game.damage_engine.deal_damage(investigator_id, horror=2)
            msg += "（同名卡被弃：受2恐惧）"
        log(f"🌠 {msg}")
        return {"pending": False, "message": "pushed_into_the_beyond"}

    if card_id == "terror_from_beyond":
        # 简化：自动选择手中数量最多的类型弃掉
        counts = {"asset": 0, "event": 0, "skill": 0}
        for cid in inv.hand:
            cd = game.state.get_card_data(cid)
            if cd is not None and cd.type.value in counts:
                counts[cd.type.value] += 1
        chosen_type = max(counts, key=counts.get) if any(counts.values()) else None
        if chosen_type:
            discarded = []
            for cid in list(inv.hand):
                cd = game.state.get_card_data(cid)
                if cd is not None and cd.type.value == chosen_type:
                    inv.hand.remove(cid)
                    inv.discard.append(cid)
                    discarded.append(game.state.card_name(cid))
            type_cn = {"asset": "支援", "event": "事件", "skill": "技能"}[chosen_type]
            log(f"👁️ 遭遇：世外诡影——弃掉所有{type_cn}手牌【{'、'.join(discarded)}】")
        else:
            log("👁️ 遭遇：世外诡影——手牌无可弃类型")
        return {"pending": False, "message": "terror_from_beyond"}

    # ---- 涌动类 ----
    if card_id == "attracting_attention":
        log("📣 遭遇：吸引注意——涌动")
        return {"pending": False, "message": "surge", "surge": True}

    if card_id == "vast_expanse":
        log("🌫️ 遭遇：辽阔无边——涌动（无异次元地点）")
        return {"pending": False, "message": "surge", "surge": True}

    if card_id == "shadow_spawned":
        log("🌑 遭遇：暗影之子——涌动")
        return {"pending": False, "message": "surge", "surge": True}

    # ---- 追獵恐魔 / 猶格之子 互动类 ----
    if card_id == "hunted_down":
        criminals = [iid for iid in _enemies_in_play(game, "罪犯") + _enemies_in_play(game, "criminal")]
        unengaged = [iid for iid in criminals if iid not in inv.threat_area]
        if not unengaged:
            log("🐺 遭遇：紧追不舍——涌动")
            return {"pending": False, "message": "surge", "surge": True}
        loc = game.state.get_location(inv.location_id)
        for iid in unengaged:
            for l in game.state.locations.values():
                if iid in l.enemies:
                    l.enemies.remove(iid)
            if iid not in inv.threat_area:
                inv.threat_area.append(iid)
            inst = game.state.get_card_instance(iid)
            cd = game.state.get_card_data(inst.card_id) if inst else None
            if cd is not None:
                game.damage_engine.deal_damage(
                    investigator_id, damage=cd.enemy_damage or 0,
                    horror=cd.enemy_horror or 0, source=iid)
        log(f"🐺 遭遇：紧追不舍——{len(unengaged)} 个罪犯敌人与你交战并立刻攻击")
        return {"pending": False, "message": "hunted_down"}

    if card_id == "slithering_behind_you":
        horrors = _enemies_in_play(game, "hunting_horror") or [
            iid for iid, inst in game.state.cards_in_play.items()
            if inst.card_id == "hunting_horror"]
        if horrors:
            inst = game.state.get_card_instance(horrors[0])
            if inst is not None:
                inst.doom += 1
            log("🐍 遭遇：尾随之蛇——追獵恐魔+1毁灭")
            controller._check_agenda_threshold()
        else:
            spawned = _spawn_specific_enemy(game, controller, "hunting_horror", inv)
            if spawned:
                log("🐍 遭遇：尾随之蛇——追獵恐魔在你地点生成并交战")
            else:
                log("🐍 遭遇：尾随之蛇——涌动")
                return {"pending": False, "message": "surge", "surge": True}
        return {"pending": False, "message": "slithering_behind_you"}

    if card_id == "stalked_in_the_dark":
        horrors = [iid for iid, inst in game.state.cards_in_play.items()
                   if inst.card_id == "hunting_horror"]
        if not horrors:
            log("🌒 遭遇：暗影潜随——涌动")
            return {"pending": False, "message": "surge", "surge": True}
        iid = horrors[0]
        inst = game.state.get_card_instance(iid)
        cd = game.state.get_card_data(inst.card_id) if inst else None
        for l in game.state.locations.values():
            if iid in l.enemies:
                l.enemies.remove(iid)
        if iid not in inv.threat_area:
            inv.threat_area.append(iid)
        if inst is not None:
            inst.exhausted = False
        if cd is not None:
            game.damage_engine.deal_damage(
                investigator_id, damage=cd.enemy_damage or 0,
                horror=cd.enemy_horror or 0, source=iid)
        log("🌒 遭遇：暗影潜随——追獵恐魔就绪、交战并攻击你")
        return {"pending": False, "message": "stalked_in_the_dark"}

    if card_id == "the_creatures_tracks":
        # 简化：自动选择受2恐惧（官方为二选一）
        log("🐾 遭遇：怪物的踪迹——受到2恐惧")
        game.damage_engine.deal_damage(investigator_id, horror=2)
        return {"pending": False, "message": "the_creatures_tracks"}

    if card_id == "towering_beasts":
        spawns = [iid for iid, inst in game.state.cards_in_play.items()
                  if inst.card_id == "brood_of_yog_sothoth"]
        if spawns:
            inst = game.state.get_card_instance(spawns[0])
            if inst is not None:
                inst.damage = max(0, inst.damage - 1)  # +1生命（简化：减伤1）
            log("🗿 遭遇：高耸的野兽——猶格之子获得强化")
            if _enemy_at_location(game, spawns[0], inv.location_id):
                game.damage_engine.deal_damage(investigator_id, damage=1)
                log("  → 同地点：受到1伤害")
        else:
            log("🗿 遭遇：高耸的野兽——场上无猶格之子")
        return {"pending": False, "message": "towering_beasts"}

    if card_id == "altered_beast":
        abominations = _enemies_in_play(game, "異形")
        if not abominations:
            log("🧬 遭遇：变异野兽——涌动")
            return {"pending": False, "message": "surge", "surge": True}
        inst = game.state.get_card_instance(abominations[0])
        if inst is not None:
            inst.damage = 0
        log(f"🧬 遭遇：变异野兽——治愈【{game.state.card_name(inst.card_id)}】所有伤害")
        return {"pending": False, "message": "altered_beast"}

    if card_id == "ruin_and_destruction":
        spawns = [iid for iid, inst in game.state.cards_in_play.items()
                  if inst.card_id == "brood_of_yog_sothoth"]
        same_loc = [iid for iid in spawns if _enemy_at_location(game, iid, inv.location_id)]
        if not same_loc:
            log("🏚️ 遭遇：破坏与毁灭——涌动")
            return {"pending": False, "message": "surge", "surge": True}
        log("🏚️ 遭遇：破坏与毁灭（敏捷3，失败按差额受伤）")
        run_test(investigator_id, skill=Skill.AGILITY, difficulty=3,
                 on_failure=lambda r: game.damage_engine.deal_damage(
                     investigator_id, damage=_margin_fail(r)))
        return {"pending": False, "message": "ruin_and_destruction"}

    # ---- 威胁区/持续类 ----
    if card_id == "cursed_luck":
        _place_in_threat(game, inv, "cursed_luck")
        log("🎲 遭遇：厄运连连——放入威胁区域（技能值-1）")
        game.state.scenario.vars.setdefault("cursed_luck", {})[investigator_id] = True
        return {"pending": False, "message": "cursed_luck"}

    if card_id == "beyond_the_veil":
        threats = game.state.scenario.vars.setdefault("beyond_the_veil", {})
        if investigator_id not in threats:
            _place_in_threat(game, inv, "beyond_the_veil")
            threats[investigator_id] = True
            log("🌉 遭遇：转生幻象——放入威胁区域，涌动")
        else:
            log("🌉 遭遇：转生幻象——涌动")
        return {"pending": False, "message": "surge", "surge": True}

    if card_id == "psychopomps_song":
        _place_in_threat(game, inv, "psychopomps_song")
        game.state.scenario.vars.setdefault("psychopomps_song", {})[investigator_id] = True
        log("🎵 遭遇：灵魂之歌——放入威胁区域（受伤害时额外+2），涌动")
        return {"pending": False, "message": "surge", "surge": True}

    if card_id == "unhallowed_country":
        _place_in_threat(game, inv, "unhallowed_country")
        game.state.scenario.vars.setdefault("unhallowed_country", {})[investigator_id] = True
        log("⛔ 遭遇：不洁之地——放入威胁区域（不能打出盟友）")
        return {"pending": False, "message": "unhallowed_country"}

    if card_id == "sordid_and_silent":
        game.state.scenario.vars.setdefault("sordid_and_silent", {})[inv.location_id] = True
        log("🤫 遭遇：忍气吞声——叠加到你所在地点")
        return {"pending": False, "message": "sordid_and_silent"}

    if card_id == "arcane_barrier":
        game.state.scenario.vars.setdefault("arcane_barrier", {})[inv.location_id] = True
        log("✨ 遭遇：奥术屏障——叠加到你所在地点")
        return {"pending": False, "message": "arcane_barrier"}

    if card_id == "light_of_aforgomon":
        game.state.scenario.vars["light_of_aforgomon"] = True
        log("💡 遭遇：亚弗戈蒙之光——叠加到密谋（伤害/恐惧视为直接）")
        return {"pending": False, "message": "light_of_aforgomon"}

    if card_id == "spaces_between":
        # 简化：弃掉非中央地点的所有线索
        central = game.state.scenario.vars.get("central_location", "")
        lost = 0
        for loc in game.state.locations.values():
            if loc.location_id != central and loc.clues > 0:
                lost += loc.clues
                loc.clues = 0
        log(f"🕳️ 遭遇：缝隙空间——非中央地点的 {lost} 个线索被弃掉")
        return {"pending": False, "message": "spaces_between"}

    if card_id == "wormhole":
        # 简化：移动到随机连接地点（遭遇堆已无地点卡）
        loc = game.state.get_location(inv.location_id)
        conns = [c for c in (getattr(loc, "connections", []) or []) if c in game.state.locations]
        if conns:
            inv.location_id = conns[0]
            log(f"🌀 遭遇：虫洞——你被吸到【{game.state.locations[conns[0]].card_data.name_cn}】")
        else:
            log("🌀 遭遇：虫洞——无处可去")
        return {"pending": False, "message": "wormhole"}

    return None


def _keywords_of(game, instance_id: str) -> list[str]:
    inst = game.state.get_card_instance(instance_id)
    if inst is None:
        return []
    cd = game.state.get_card_data(inst.card_id)
    if cd is None:
        return []
    return list(getattr(cd, "keywords", None) or []) + list(getattr(cd, "traits", None) or [])


def _place_in_threat(game, inv, card_id: str) -> None:
    from backend.models.state import CardInstance
    inst_id = game.state.next_instance_id()
    ci = CardInstance(
        instance_id=inst_id, card_id=card_id,
        owner_id=inv.investigator_id, controller_id=inv.investigator_id,
    )
    game.state.cards_in_play[inst_id] = ci
    inv.threat_area.append(inst_id)


def _enemy_at_location(game, instance_id: str, location_id: str) -> bool:
    loc = game.state.get_location(location_id)
    if loc is not None and instance_id in loc.enemies:
        return True
    for inv in game.state.investigators.values():
        if inv.location_id == location_id and instance_id in inv.threat_area:
            return True
    return False


def _spawn_specific_enemy(game, controller, card_id: str, inv) -> bool:
    """从遭遇牌堆/弃牌堆找特定敌人生成在调查员地点并交战。"""
    scen = game.state.scenario
    found = None
    for pile in (scen.encounter_deck, scen.encounter_discard):
        if card_id in pile:
            pile.remove(card_id)
            found = card_id
            break
    if found is None:
        return False
    from backend.models.state import CardInstance
    iid = game.state.next_instance_id()
    ci = CardInstance(
        instance_id=iid, card_id=card_id,
        owner_id="scenario", controller_id="scenario",
    )
    game.state.cards_in_play[iid] = ci
    inv.threat_area.append(iid)
    random.shuffle(scen.encounter_deck)
    return True
