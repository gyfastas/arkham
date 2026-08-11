"""Edge of the Earth（地极秘境）剧本混沌标记（符号 token）效果。

覆盖剧本（sid 按参考卡 encounter_code 归组，part 后缀归一到组）：

- ``ice_and_death_part_1/2/3`` → 组 ``ice_and_death``（参考卡 08501）
- ``to_the_forbidden_peaks``（08596）
- ``city_of_the_elder_things``（08621）
- ``endless_night`` —— 插曲 II，纯剧情无参考卡 → ``apply_token`` 返回 False
- ``fatal_mirage``（08549）
- ``the_heart_of_madness_part_1`` → 组 ``the_heart_of_madness``（08648）
- ``final_night`` —— 插曲 III，纯剧情无参考卡 → 返回 False

官方文本来源：``data/encounter_cards/edge_of_the_earth.json`` 中 scenario 卡的
``text``（Easy/Standard 面）/ ``back_text``（Hard/Expert 面），以英文为准；
``.tools/arkham-cards-data/chaos_tokens.json`` 仅作结构化参考。

frost 标记：5 张参考卡均未给 frost 自身定义额外效果，其在 EOE 中固定为 -1
（``CHAOS_TOKEN_VALUES[ChaosTokenType.FROST] == -1``，引擎已处理数值），因此
本模块不设 frost 的剧本分支；仅 city_of_the_elder_things 石板与
the_heart_of_madness 异教徒会引用 frost（见各分支注释）。

简化项（官方为玩家选择或机制尚未建模时，自动取最确定/最有利分支）：

- 地点「庇护值」(shelter)：EOE 卡牌数据未结构化该字段，依次尝试
  ``card_data.shelter`` 属性、英文文本 ``<b>Shelter X.</b>``、中文文本
  ``庇護X``；都无法确定时视为 0。
- 地点「层数」(level)：取地点 ``CardData.level``（地点默认 0，未建模）。
- Tekeli-li 牌堆：存于 ``scenario.vars["tekeli_li_deck"]``（牌堆顶 = 下标 0）。
  「洗入你的牌库」= 插入牌库随机位置（不看）；「抽 Tekeli-li 顶牌」= 入手。
- 钥匙 (keys)：``scenario.vars["keys_controlled"] = {调查员id: 数量}``；
  放到地点后记入 ``vars["keys_on_locations"] = {地点id: 数量}``。
- 胜利区「故事卡」：仅统计 asset 类型的卡（卡牌数据无 story 标志字段）。
- 「你正下方的地点」：相连地点中 level 严格更小且最大者；无则不动。
- 「失去 1 个 Expedition 支援控制权并放到地点」：自动选费用最低者，
  作为地点 attachment（沿用 location attachments 机制）。
- fatal_mirage 石板「二选一」：优先洗 Tekeli-li 顶牌入牌库（避免强制位移），
  无法洗时移动到 Prison of Memories（该地点需在场）。
- 敌人「朝你移动一次」：沿 BFS 最短路走一步；已与你交战则改为攻击你。
- city_of_the_elder_things 石板的「本次检定揭示过 frost」：当前引擎每次检定
  只揭示 1 个标记且无记录，读 ``ctx.extra["frost_revealed"]``（由集成方/卡牌
  效果设置），默认 False。
"""

from __future__ import annotations

import re

from backend.models.enums import ChaosTokenType
from backend.models.state import is_weakness_card

_SYMBOL_TOKENS = (
    ChaosTokenType.SKULL,
    ChaosTokenType.CULTIST,
    ChaosTokenType.TABLET,
    ChaosTokenType.ELDER_THING,
)

#: 归组后拥有符号效果的 EOE 剧本组（插曲 endless_night/final_night 除外）
_EOE_GROUPS = {
    "ice_and_death",
    "to_the_forbidden_peaks",
    "city_of_the_elder_things",
    "fatal_mirage",
    "the_heart_of_madness",
}


def _eoe_group(scenario_id: str) -> str | None:
    """把 part 后缀归一到剧本组；非 EOE（或纯剧情插曲）返回 None。"""
    sid = scenario_id or ""
    if sid.startswith("ice_and_death"):
        return "ice_and_death"
    if sid.startswith("the_heart_of_madness"):
        return "the_heart_of_madness"
    if sid in ("to_the_forbidden_peaks", "city_of_the_elder_things", "fatal_mirage"):
        return sid
    return None


# ---------------------------------------------------------------------------
# 模块内辅助（自足实现，兼容英文 traits：trait 小写并把空格转为下划线后视同 keyword）
# ---------------------------------------------------------------------------

def _card_keywords(cd) -> set[str]:
    """CardData 的关键词集合：keywords 字段 ∪ 规范化后的英文 traits。"""
    kws = set(getattr(cd, "keywords", None) or [])
    for trait in getattr(cd, "traits", None) or []:
        kws.add(str(trait).lower().replace(" ", "_"))
    return kws


def _enemy_matches(controller, instance_id: str, keyword: str | None) -> bool:
    inst = controller.game_state.get_card_instance(instance_id)
    if inst is None:
        return False
    cd = controller.game_state.get_card_data(inst.card_id)
    if cd is None or cd.type.value != "enemy":
        return False
    return keyword is None or keyword in _card_keywords(cd)


def _count_enemies_at(controller, location_id: str, keyword: str) -> int:
    """某地点（含与该地点调查员交战）匹配 keyword 的敌人数。"""
    gs = controller.game_state
    count = 0
    loc = gs.get_location(location_id)
    if loc is not None:
        count += sum(1 for iid in loc.enemies if _enemy_matches(controller, iid, keyword))
    for inv in gs.investigators.values():
        if inv.location_id != location_id:
            continue
        count += sum(1 for iid in inv.threat_area
                     if _enemy_matches(controller, iid, keyword))
    return count


def _nearest_enemy(controller, inv, keyword: str | None) -> str | None:
    """最近的匹配敌人：与你交战 > 同地点 > 任意在场。"""
    gs = controller.game_state
    for iid in inv.threat_area:
        if _enemy_matches(controller, iid, keyword):
            return iid
    loc = gs.get_location(inv.location_id)
    if loc is not None:
        for iid in loc.enemies:
            if _enemy_matches(controller, iid, keyword):
                return iid
    for iid in gs.cards_in_play:
        if _enemy_matches(controller, iid, keyword):
            return iid
    return None


def _enemy_location(controller, instance_id: str) -> str | None:
    """敌人所在的未交战地点 id（交战中则返回 None）。"""
    for lid, loc in controller.game_state.locations.items():
        if instance_id in loc.enemies:
            return lid
    return None


def _move_enemy_toward(controller, instance_id: str, target_location_id: str) -> str | None:
    """敌人沿最短路朝目标地点走一步；返回新地点 id（无法移动返回 None）。"""
    gs = controller.game_state
    cur = _enemy_location(controller, instance_id)
    if cur is None or cur == target_location_id:
        return None
    loc = gs.get_location(cur)
    if loc is None:
        return None
    cur_dist = controller._bfs_distance(cur, target_location_id)
    best = None
    best_dist = cur_dist
    for conn in loc.connections:
        if gs.get_location(conn) is None:
            continue
        if conn == target_location_id:
            best = conn
            break
        d = controller._bfs_distance(conn, target_location_id)
        if d and (best is None or d < best_dist):
            best, best_dist = conn, d
    if best is None:
        return None
    loc.enemies.remove(instance_id)
    gs.get_location(best).enemies.append(instance_id)
    return best


def _enemy_attack(controller, instance_id: str, inv) -> None:
    """敌人立刻攻击：按卡牌印刷值造成伤害/恐惧。"""
    inst = controller.game_state.get_card_instance(instance_id)
    cd = controller.game_state.get_card_data(inst.card_id) if inst else None
    if cd is None:
        return
    inv.damage += cd.enemy_damage or 0
    inv.horror += cd.enemy_horror or 0


def _shelter_value(controller, location_id: str) -> int:
    """地点庇护值：CardData.shelter 属性 → 英文 ``Shelter X`` → 中文 ``庇護X`` → 0。"""
    loc = controller.game_state.get_location(location_id)
    cd = loc.card_data if loc else None
    if cd is None:
        return 0
    val = getattr(cd, "shelter", None)
    if val is not None:
        return int(val)
    m = re.search(r"Shelter\s+(\d+)", cd.text or "")
    if m is None:
        m = re.search(r"庇護\s*(\d+)", getattr(cd, "text_cn", "") or "")
    return int(m.group(1)) if m else 0


def _location_level(controller, location_id: str) -> int:
    """地点层数（Forbidden Peaks 机制；未建模时默认 0）。"""
    loc = controller.game_state.get_location(location_id)
    cd = loc.card_data if loc else None
    return int(getattr(cd, "level", 0) or 0) if cd else 0


def _location_below(controller, location_id: str) -> str | None:
    """「正下方」的地点：相连且 level 严格更小者中 level 最大的一个。"""
    gs = controller.game_state
    loc = gs.get_location(location_id)
    if loc is None:
        return None
    cur_level = _location_level(controller, location_id)
    best = None
    best_level = -1
    for conn in loc.connections:
        if gs.get_location(conn) is None:
            continue
        lv = _location_level(controller, conn)
        if lv < cur_level and lv > best_level:
            best, best_level = conn, lv
    return best


def _tekeli_li_deck(controller) -> list:
    return controller.s.vars.setdefault("tekeli_li_deck", [])


def _shuffle_tekeli_li_top_into_deck(controller, inv) -> bool:
    """将 Tekeli-li 牌堆顶洗入调查员牌库（不看 = 随机位置）。牌堆空返回 False。"""
    deck = _tekeli_li_deck(controller)
    if not deck:
        return False
    card_id = deck.pop(0)
    import random
    inv.deck.insert(random.randint(0, len(inv.deck)), card_id)
    return True


def _draw_tekeli_li_top(controller, inv) -> str | None:
    """抽 Tekeli-li 牌堆顶（简化：放入手牌）。牌堆空返回 None。"""
    deck = _tekeli_li_deck(controller)
    if not deck:
        return None
    card_id = deck.pop(0)
    inv.hand.append(card_id)
    return card_id


def _keys_controlled(controller, investigator_id: str) -> int:
    keys = controller.s.vars.get("keys_controlled") or {}
    return int(keys.get(investigator_id, 0) or 0)


def _place_key_on_location(controller, investigator_id: str, location_id: str) -> bool:
    """将你控制的 1 把钥匙放到所在地点。没有钥匙返回 False。"""
    keys = controller.s.vars.setdefault("keys_controlled", {})
    if int(keys.get(investigator_id, 0) or 0) <= 0:
        return False
    keys[investigator_id] = int(keys.get(investigator_id, 0)) - 1
    on_locs = controller.s.vars.setdefault("keys_on_locations", {})
    on_locs[location_id] = int(on_locs.get(location_id, 0) or 0) + 1
    return True


def _story_cards_in_victory(controller) -> int:
    """胜利区中的故事卡数量（简化：仅统计 asset 类型）。"""
    gs = controller.game_state
    count = 0
    for cid in gs.scenario.victory_display:
        cd = gs.get_card_data(cid)
        if cd is not None and cd.type.value == "asset":
            count += 1
    return count


def _seal_or_mist_pylon(controller, location_id: str) -> bool:
    """所在地点有印记（seal）或为 Mist-Pylon。

    简化：seal 机制未建模，依次检查 vars["sealed_locations"] 集合与
    地点 attachment 中卡 id 含 "seal" 的卡；Mist-Pylon 按卡 id 前缀判断。
    """
    gs = controller.game_state
    loc = gs.get_location(location_id)
    if loc is None or loc.card_data is None:
        return False
    if loc.card_data.id.startswith("mist_pylon"):
        return True
    if location_id in (controller.s.vars.get("sealed_locations") or ()):
        return True
    return any("seal" in cid for cid in loc.attachment_card_ids(gs))


def _fail_margin(ctx) -> int:
    """失败的差值（难度 - 修正后技能值，下限 0）。"""
    return max(0, (ctx.difficulty or 0) - (ctx.modified_skill or 0))


def _move_or_attack_nearest(controller, ctx, inv, keyword: str | None, label: str) -> None:
    """最近的匹配敌人朝你移动一次；若已与你交战则改为攻击你。"""
    iid = _nearest_enemy(controller, inv, keyword)
    if iid is None:
        return
    inst = controller.game_state.get_card_instance(iid)
    cd = controller.game_state.get_card_data(inst.card_id) if inst else None
    name = (cd.name_cn or cd.name) if cd else iid
    if iid in inv.threat_area:
        _enemy_attack(controller, iid, inv)
        ctx.game_state.log_effect(f"💀 {label}：与你交战的《{name}》立刻攻击你")
        return
    moved = _move_enemy_toward(controller, iid, inv.location_id)
    if moved:
        ctx.game_state.log_effect(f"💀 {label}：《{name}》朝你移动一次")


def _move_investigator_below(controller, ctx, inv) -> None:
    """移动到正下方的地点（见模块 docstring 简化说明）。"""
    dest = _location_below(controller, inv.location_id)
    if dest is None:
        return
    inv.location_id = dest
    cd = controller.game_state.get_card_data(dest)
    ctx.game_state.log_effect(f"💀 标记效果：你移动到正下方的【{(cd.name_cn or cd.name) if cd else dest}】")


def _fm_move_to_prison_or_shuffle_tekeli(controller, ctx, inv) -> None:
    """Fatal Mirage 石板二选一（简化：优先洗 Tekeli-li，无法洗时移动到囚忆监狱）。"""
    if _shuffle_tekeli_li_top_into_deck(controller, inv):
        ctx.game_state.log_effect("💀 石板失败效果：Tekeli-li 牌堆顶洗入你的牌库（二选一自动取此项）")
        return
    gs = controller.game_state
    if "prison_of_memories" in gs.locations:
        inv.location_id = "prison_of_memories"
        ctx.game_state.log_effect("💀 石板失败效果：你移动到【囚忆监狱】（Tekeli-li 牌堆为空）")


def _lose_expedition_asset_to_location(controller, ctx, inv) -> None:
    """失去 1 个 Expedition 支援控制权并放到所在地点（简化：自动选费用最低者）。"""
    gs = controller.game_state
    cheapest = None
    cheapest_cost = 999
    for iid in inv.play_area:
        inst = gs.get_card_instance(iid)
        cd = gs.get_card_data(inst.card_id) if inst else None
        if cd is None or cd.type.value != "asset":
            continue
        if "expedition" not in _card_keywords(cd):
            continue
        if (cd.cost or 0) < cheapest_cost:
            cheapest, cheapest_cost = iid, (cd.cost or 0)
    if cheapest is None:
        return
    inst = gs.get_card_instance(cheapest)
    cd = gs.get_card_data(inst.card_id)
    inv.play_area.remove(cheapest)
    mgr = getattr(controller.game, "slot_managers", {}).get(ctx.investigator_id)
    if mgr:
        mgr.vacate(cheapest)
    loc = gs.get_location(inv.location_id)
    if loc is not None:
        inst.attached_to = inv.location_id
        loc.attachments.append(cheapest)
    ctx.game_state.log_effect(
        f"💀 石板失败效果：失去《{(cd.name_cn or cd.name) if cd else inst.card_id}》控制权，放到所在地点（自动选最低费）"
    )


def _discard_deck_top_drawing_weaknesses(controller, ctx, inv, n: int) -> None:
    """弃牌库顶 n 张，其中弱点入手（Ice and Death 石板）。"""
    discarded = controller._discard_top_of_deck(inv, n)
    drawn = []
    for cid in discarded:
        cd = controller.game_state.get_card_data(cid)
        if is_weakness_card(cd):
            inv.discard.remove(cid)
            inv.hand.append(cid)
            drawn.append(cd.name_cn or cd.name if cd else cid)
    msg = f"💀 石板失败效果：弃牌库顶{len(discarded)}张"
    if drawn:
        msg += f"，弱点入手（{'、'.join(drawn)}）"
    ctx.game_state.log_effect(msg)


# ---------------------------------------------------------------------------
# 入口：标记揭示时
# ---------------------------------------------------------------------------

def apply_token(controller, ctx, inv, pending, success_pending) -> bool:
    """应用 EOE 剧本的符号标记效果。返回 True 表示本模块已处理该标记。

    ``pending`` / ``success_pending`` 为按调查员区分的待结算效果集合
    （与 official_core 的 ``_token_pending`` / ``_token_success_pending`` 同构），
    失败/成功时分别由 :func:`on_fail` / :func:`on_success` 结算。
    """
    group = _eoe_group(getattr(controller.s, "scenario_id", ""))
    if group is None or inv is None:
        return False
    token = ctx.chaos_token
    if token not in _SYMBOL_TOKENS:
        return False
    hard = controller._is_hard_difficulty

    if group == "ice_and_death":
        _iad_apply(controller, ctx, inv, pending, hard)
    elif group == "fatal_mirage":
        _fm_apply(controller, ctx, inv, pending, success_pending, hard)
    elif group == "to_the_forbidden_peaks":
        _ttp_apply(controller, ctx, inv, pending, success_pending, hard)
    elif group == "city_of_the_elder_things":
        _cotet_apply(controller, ctx, inv, pending, hard)
    elif group == "the_heart_of_madness":
        _thom_apply(controller, ctx, inv, pending, hard)

    if ctx.extra.get("token_text"):
        ctx.game_state.log_effect(f"🎲 标记效果：{ctx.extra['token_text']}")
    return True


def _iad_apply(controller, ctx, inv, pending, hard: bool) -> None:
    """Ice and Death（08501）。"""
    token = ctx.chaos_token
    if token == ChaosTokenType.SKULL:
        shelter = _shelter_value(controller, inv.location_id)
        x = shelter if hard else -(-shelter // 2)  # 标准面：庇护值的一半（向上取整）
        if x:
            ctx.modify_amount(-x, "iad_skull")
        ctx.extra["token_text"] = (
            f"骷髅 -{x}（地点庇护值{shelter}" + ("" if hard else "的一半，向上取整") + "）"
        )
    elif token == ChaosTokenType.CULTIST:
        ctx.modify_amount(-2, "iad_cultist")
        if hard:
            pending.add("iad_cultist_tekeli_margin")
            ctx.extra["token_text"] = (
                "异教徒 -2，若失败：每低1点将Tekeli-li牌堆顶1张洗入你的牌库"
                "（每有1张不能洗则受1恐惧）"
            )
        else:
            pending.add("iad_cultist_tekeli")
            ctx.extra["token_text"] = (
                "异教徒 -2，若失败：将Tekeli-li牌堆顶1张洗入你的牌库（不能洗则受1恐惧）"
            )
    elif token == ChaosTokenType.TABLET:
        ctx.modify_amount(-4 if hard else -3, "iad_tablet")
        pending.add("iad_tablet_discard_margin")
        ctx.extra["token_text"] = (
            f"石板 {-4 if hard else -3}，若失败：每低1点弃牌库顶1张，以此弃掉的弱点入手"
        )


def _fm_apply(controller, ctx, inv, pending, success_pending, hard: bool) -> None:
    """Fatal Mirage（08549）。"""
    token = ctx.chaos_token
    if token == ChaosTokenType.SKULL:
        story = _story_cards_in_victory(controller)
        agenda_no = (controller.s.current_agenda_index or 0) + 1
        x = story + agenda_no if hard else story
        if x:
            ctx.modify_amount(-x, "fm_skull")
        ctx.extra["token_text"] = (
            f"骷髅 -{x}（胜利区故事卡×{story}" + (f"，当前密谋编号+{agenda_no}" if hard else "") + "）"
        )
    elif token == ChaosTokenType.CULTIST:
        ctx.modify_amount(-2, "fm_cultist")
        if hard:
            pending.add("fm_cultist_clue_hard")
            success_pending.add("fm_cultist_clue_hard")
            ctx.extra["token_text"] = "异教徒 -2，若未成功至少2点：将你的1个线索放到所在地点"
        else:
            pending.add("fm_cultist_clue_fail")
            ctx.extra["token_text"] = "异教徒 -2，若失败：将你的1个线索放到所在地点"
    elif token == ChaosTokenType.TABLET:
        ctx.modify_amount(-4 if hard else -3, "fm_tablet")
        pending.add("fm_tablet_choice")
        ctx.extra["token_text"] = (
            f"石板 {-4 if hard else -3}，若失败：移动到囚忆监狱或将Tekeli-li牌堆顶"
            "洗入你的牌库（二选一）" + ("；若失败2点以上则两者皆执行" if hard else "")
        )
    elif token == ChaosTokenType.ELDER_THING:
        ctx.modify_amount(-5 if hard else -4, "fm_elder_thing")
        pending.add("fm_elder_doom_eidolon")
        ctx.extra["token_text"] = (
            f"旧神之物 {-5 if hard else -4}，若失败：场上1个Eidolon敌人+1毁灭"
        )


def _ttp_apply(controller, ctx, inv, pending, success_pending, hard: bool) -> None:
    """To the Forbidden Peaks（08596）。"""
    token = ctx.chaos_token
    if token == ChaosTokenType.SKULL:
        level = _location_level(controller, inv.location_id)
        x = level + 2 if hard else level
        if x:
            ctx.modify_amount(-x, "ttp_skull")
        ctx.extra["token_text"] = f"骷髅 -{x}（地点层数{level}" + ("+2" if hard else "") + "）"
    elif token == ChaosTokenType.CULTIST:
        ctx.modify_amount(-1, "ttp_cultist")
        # 困难面为无条件效果，但仍是「检定结束后」移动 → 成功/失败都挂延迟结算
        pending.add("ttp_cultist_move_down")
        if hard:
            success_pending.add("ttp_cultist_move_down")
        ctx.extra["token_text"] = (
            "异教徒 -1，" + ("" if hard else "若失败：") + "本检定结束后移动到你正下方的地点"
        )
    elif token == ChaosTokenType.TABLET:
        ctx.modify_amount(-4 if hard else -3, "ttp_tablet")
        pending.add("ttp_tablet_expedition")
        ctx.extra["token_text"] = (
            f"石板 {-4 if hard else -3}，若失败：失去1个Expedition支援控制权并放到所在地点"
        )
    elif token == ChaosTokenType.ELDER_THING:
        ctx.modify_amount(-5 if hard else -4, "ttp_elder_thing")
        pending.add("ttp_elder_thing_move")
        ctx.extra["token_text"] = (
            f"旧神之物 {-5 if hard else -4}，若失败：最近的Elder Thing敌人朝你移动一次"
            "（已与你交战则攻击你）"
        )


def _cotet_apply(controller, ctx, inv, pending, hard: bool) -> None:
    """City of the Elder Things（08621）。"""
    token = ctx.chaos_token
    if token == ChaosTokenType.SKULL:
        keys = _keys_controlled(controller, ctx.investigator_id)
        x = keys + 2 if hard else keys
        if x:
            ctx.modify_amount(-x, "cotet_skull")
        ctx.extra["token_text"] = f"骷髅 -{x}（你控制的钥匙×{keys}" + ("+2" if hard else "") + "）"
    elif token == ChaosTokenType.CULTIST:
        ctx.modify_amount(-2, "cotet_cultist")
        if hard:
            # 困难面为无条件效果，立即结算
            if _place_key_on_location(controller, ctx.investigator_id, inv.location_id):
                ctx.extra["token_text"] = "异教徒 -2，将你控制的1把钥匙放到所在地点"
            else:
                ctx.extra["token_text"] = "异教徒 -2（你没有钥匙可放）"
        else:
            pending.add("cotet_cultist_key")
            ctx.extra["token_text"] = "异教徒 -2，若失败：将你控制的1把钥匙放到所在地点"
    elif token == ChaosTokenType.TABLET:
        frost = bool(ctx.extra.get("frost_revealed"))
        if frost:
            # 「改为自动失败」：不取数值修正；困难面额外受1伤害
            ctx.extra["force_auto_fail"] = True
            if hard:
                inv.damage += 1
                ctx.extra["token_text"] = "石板 本检定揭示过[frost]：受1伤害并自动失败"
            else:
                ctx.extra["token_text"] = "石板 本检定揭示过[frost]：改为自动失败"
        else:
            ctx.modify_amount(-4 if hard else -3, "cotet_tablet")
            ctx.extra["token_text"] = (
                f"石板 {-4 if hard else -3}（若本检定揭示过[frost]则改为自动失败）"
            )
    elif token == ChaosTokenType.ELDER_THING:
        ctx.modify_amount(-5 if hard else -4, "cotet_elder_thing")
        pending.add("cotet_elder_enemy_move")
        ctx.extra["token_text"] = (
            f"旧神之物 {-5 if hard else -4}，若失败：最近的敌人朝你移动一次"
            "（已与你交战则攻击你）"
        )


def _thom_apply(controller, ctx, inv, pending, hard: bool) -> None:
    """The Heart of Madness（08648）。"""
    token = ctx.chaos_token
    if token == ChaosTokenType.SKULL:
        ao = _count_enemies_at(controller, inv.location_id, "ancient_one") > 0
        x = (4 if ao else 2) if hard else (3 if ao else 1)
        ctx.modify_amount(-x, "thom_skull")
        ctx.extra["token_text"] = f"骷髅 -{x}" + ("（Ancient One敌人在你地点）" if ao else "")
    elif token == ChaosTokenType.CULTIST:
        ctx.modify_amount(-1, "thom_cultist")
        if _seal_or_mist_pylon(controller, inv.location_id):
            # 视为[frost]：frost 数值同为 -1，修正不变；置标志供其他效果（如
            # Heavy Furs、地点能力）识别。标准面为「改为视为」，困难面为「同时视为」。
            ctx.extra["treat_token_as_frost"] = True
            ctx.extra["token_text"] = (
                "异教徒 -1（地点有印记或为Mist-Pylon：" + ("同时" if hard else "改为") + "视为[frost]）"
            )
        else:
            ctx.extra["token_text"] = "异教徒 -1"
    elif token == ChaosTokenType.TABLET:
        ctx.modify_amount(-3, "thom_tablet")
        if hard:
            # 困难面为无条件效果，立即结算
            drawn = _draw_tekeli_li_top(controller, inv)
            ctx.extra["token_text"] = (
                "石板 -3，抽Tekeli-li牌堆顶1张" if drawn else "石板 -3（Tekeli-li牌堆为空）"
            )
        else:
            pending.add("thom_tablet_tekeli")
            ctx.extra["token_text"] = "石板 -3，若失败：抽Tekeli-li牌堆顶1张"
    elif token == ChaosTokenType.ELDER_THING:
        ctx.modify_amount(-5 if hard else -4, "thom_elder_thing")
        pending.add("thom_elder_doom_margin3")
        ctx.extra["token_text"] = (
            f"旧神之物 {-5 if hard else -4}，若失败3点以上：当前密谋+1毁灭（可推进密谋）"
        )


# ---------------------------------------------------------------------------
# 出口：检定失败/成功时结算延迟效果
# ---------------------------------------------------------------------------

def on_fail(controller, ctx, pending) -> None:
    """结算 EOE 符号标记的「若失败」延迟效果。"""
    if not pending:
        return
    inv = ctx.game_state.get_investigator(ctx.investigator_id)
    if inv is None:
        return
    margin = _fail_margin(ctx)

    # --- Ice and Death ---
    if "iad_cultist_tekeli" in pending:
        if _shuffle_tekeli_li_top_into_deck(controller, inv):
            ctx.game_state.log_effect("💀 异教徒失败效果：Tekeli-li 牌堆顶洗入你的牌库")
        else:
            inv.horror += 1
            ctx.game_state.log_effect("💀 异教徒失败效果：Tekeli-li 牌堆为空，受1恐惧")
        pending.discard("iad_cultist_tekeli")
    if "iad_cultist_tekeli_margin" in pending:
        shuffled = 0
        horror = 0
        for _ in range(margin):
            if _shuffle_tekeli_li_top_into_deck(controller, inv):
                shuffled += 1
            else:
                horror += 1
        inv.horror += horror
        ctx.game_state.log_effect(
            f"💀 异教徒失败效果：洗入{shuffled}张Tekeli-li" + (f"，{horror}张不能洗受{horror}恐惧" if horror else "")
        )
        pending.discard("iad_cultist_tekeli_margin")
    if "iad_tablet_discard_margin" in pending:
        if margin:
            _discard_deck_top_drawing_weaknesses(controller, ctx, inv, margin)
        pending.discard("iad_tablet_discard_margin")

    # --- Fatal Mirage ---
    if "fm_cultist_clue_fail" in pending or "fm_cultist_clue_hard" in pending:
        _fm_place_clue(controller, inv)
        pending.discard("fm_cultist_clue_fail")
        pending.discard("fm_cultist_clue_hard")
    if "fm_tablet_choice" in pending:
        if controller._is_hard_difficulty and margin >= 2:
            if _shuffle_tekeli_li_top_into_deck(controller, inv):
                ctx.game_state.log_effect("💀 石板失败效果（失败2点以上）：Tekeli-li 牌堆顶洗入你的牌库")
            gs = controller.game_state
            if "prison_of_memories" in gs.locations:
                inv.location_id = "prison_of_memories"
                ctx.game_state.log_effect("💀 石板失败效果（失败2点以上）：你移动到【囚忆监狱】")
        else:
            _fm_move_to_prison_or_shuffle_tekeli(controller, ctx, inv)
        pending.discard("fm_tablet_choice")
    if "fm_elder_doom_eidolon" in pending:
        iid = _nearest_enemy(controller, inv, "eidolon")
        if iid is not None:
            inst = controller.game_state.get_card_instance(iid)
            if inst is not None:
                inst.doom += 1
                cd = controller.game_state.get_card_data(inst.card_id)
                ctx.game_state.log_effect(
                    f"💀 旧神之物失败效果：《{(cd.name_cn or cd.name) if cd else inst.card_id}》+1毁灭（自动取最近）"
                )
        pending.discard("fm_elder_doom_eidolon")

    # --- To the Forbidden Peaks ---
    if "ttp_cultist_move_down" in pending:
        _move_investigator_below(controller, ctx, inv)
        pending.discard("ttp_cultist_move_down")
    if "ttp_tablet_expedition" in pending:
        _lose_expedition_asset_to_location(controller, ctx, inv)
        pending.discard("ttp_tablet_expedition")
    if "ttp_elder_thing_move" in pending:
        _move_or_attack_nearest(controller, ctx, inv, "elder_thing", "旧神之物失败效果")
        pending.discard("ttp_elder_thing_move")

    # --- City of the Elder Things ---
    if "cotet_cultist_key" in pending:
        if _place_key_on_location(controller, ctx.investigator_id, inv.location_id):
            ctx.game_state.log_effect("💀 异教徒失败效果：你控制的1把钥匙放到所在地点")
        pending.discard("cotet_cultist_key")
    if "cotet_elder_enemy_move" in pending:
        _move_or_attack_nearest(controller, ctx, inv, None, "旧神之物失败效果")
        pending.discard("cotet_elder_enemy_move")

    # --- The Heart of Madness ---
    if "thom_tablet_tekeli" in pending:
        drawn = _draw_tekeli_li_top(controller, inv)
        if drawn:
            cd = controller.game_state.get_card_data(drawn)
            ctx.game_state.log_effect(f"💀 石板失败效果：抽Tekeli-li《{(cd.name_cn or cd.name) if cd else drawn}》")
        pending.discard("thom_tablet_tekeli")
    if "thom_elder_doom_margin3" in pending:
        if margin >= 3:
            ctx.game_state.scenario.doom_on_agenda += 1
            controller._check_agenda_threshold()
            ctx.game_state.log_effect("💀 旧神之物失败效果（失败3点以上）：当前密谋+1毁灭")
        pending.discard("thom_elder_doom_margin3")


def on_success(controller, ctx, pending) -> None:
    """结算 EOE 符号标记的成功时延迟效果（困难面条件：未成功至少 N 点等）。"""
    if not pending:
        return
    inv = ctx.game_state.get_investigator(ctx.investigator_id)
    if inv is None:
        return
    margin = (ctx.modified_skill or 0) - (ctx.difficulty or 0)

    # Fatal Mirage 异教徒（困难）：未成功至少2点 → 放线索
    if "fm_cultist_clue_hard" in pending:
        if margin < 2:
            _fm_place_clue(controller, inv)
        pending.discard("fm_cultist_clue_hard")
    # Forbidden Peaks 异教徒（困难）：检定结束后移动到正下方（无条件）
    if "ttp_cultist_move_down" in pending:
        _move_investigator_below(controller, ctx, inv)
        pending.discard("ttp_cultist_move_down")


def _fm_place_clue(controller, inv) -> None:
    """将你的 1 个线索放到所在地点（Fatal Mirage 异教徒）。"""
    if inv.clues > 0:
        inv.clues -= 1
        loc = controller.game_state.get_location(inv.location_id)
        if loc is not None:
            loc.clues += 1
        controller.game_state.log_effect("💀 异教徒效果：你的1个线索放到所在地点")
