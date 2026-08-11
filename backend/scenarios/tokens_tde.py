"""食梦者 (The Dream-Eaters) 八章符号标记效果。

官方文本来源：`data/encounter_cards/the_dream_eaters.json` 的 scenario 卡
`text`（Easy/Standard 正面）与 `back_text`（Hard/Expert 背面）；结构化参考
`.tools/arkham-cards-data/chaos_tokens.json`。冲突以卡面为准。

注意：数据层剧本卡 id 为 `where_the_gods_dwell`（arkhamdb 06286），项目内部
剧本 id 为 `where_gods_dwell`（见 data/campaigns/the_dream_eaters.json），
本模块以项目内部 id 为准。

调用约定（与 official_core 的 _dunwich/_carcosa、tokens_tic 一致）：
- `apply_token(controller, ctx, inv, pending, success_pending) -> bool`
  在 CHAOS_TOKEN_RESOLVED 时调用；返回 True 表示该剧本+标记已处理。
- `on_fail(controller, ctx, pending)` 在 SKILL_TEST_FAILED 时结算 pending 标记。
- `on_success(controller, ctx, pending)` 在 SKILL_TEST_SUCCESSFUL 时结算。

TDE 特有机制的简化表示（引擎未实现这些机制，状态存于 `scenario.vars`）：
- `dream_side`: "dream" | "waking"  梦境/清醒双线（战役层记录即可，标记效果不读取）。
- `infested_locations`: list[str]  被侵染地点（Waking Nightmare）。
- `infestation_tests_made`: int  已进行的侵染检定次数（侵染袋机制未实现，
  “make an infestation test” 仅计数 + 日志）。
- `signs_of_gods`: int  调查员已发现的神之印记数（The Search for Kadath）。
- `alarm_levels`: {inv_id: int}  各调查员警报等级（Dark Side of the Moon）。
- `scenario_card_damage`: int  剧本参考卡上的伤害（Point of No Return 骷髅）。
- `swarm_cards`: {instance_id: int}  敌人身上附加的蜂群卡数（蜂群机制未实现，
  仅计数，不影响战斗值）。
- `shroud_bonus_round`: {location_id: int}  本轮临时隐蔽值加成
  （Search for Kadath 异教徒；回合结束清除未挂钩，由剧本层负责）。
- `token_drawn_encounters`: list[str]  标记效果“抽遭遇牌堆顶”抽到的卡
  （简化：移出牌堆并记录，不逐张结算遭遇效果）。

简化项（均自动取对玩家最有利/最常用的分支）：
- 选择类效果自动选择：the_search_for_kadath 石板（受1伤害1恐惧 vs 密谋+1毁灭）
  不致败则受伤，否则放毁灭；a_thousand_shapes_of_horror 旧神之物
  （放1线索 vs 受1伤害）不致败则受伤，否则放线索。
- a_thousand_shapes_of_horror 石板自动选战斗值最高且 ≤ 成功超出值的敌人躲避。
- point_of_no_return 旧神之物自动选攻击（伤害+恐惧）最弱的就绪敌人。
- where_gods_dwell 石板自动取手牌中第一只奈亚拉托提普。
- “调查期间”按智力检定、“攻击/躲避”按战斗/敏捷检定推断。
- 敌人“立刻攻击”直接按卡面伤害/恐惧加到调查员（与 official_core 一致，
  不走 damage_engine 事件流）。
- The Unnamable 敌人卡不在数据层：按 id `the_unnamable` 或英文名匹配。
"""

from __future__ import annotations

import random
from typing import Any

from backend.models.enums import CHAOS_TOKEN_VALUES, ChaosTokenType, Skill

TDE_SCENARIO_IDS = {
    "beyond_the_gates_of_sleep",
    "waking_nightmare",
    "the_search_for_kadath",
    "a_thousand_shapes_of_horror",
    "dark_side_of_the_moon",
    "point_of_no_return",
    "where_gods_dwell",
    "weaver_of_the_cosmos",
}

_SYMBOL_TOKENS = (
    ChaosTokenType.SKULL,
    ChaosTokenType.CULTIST,
    ChaosTokenType.TABLET,
    ChaosTokenType.ELDER_THING,
)


# ---------------------------------------------------------------------------
# 通用辅助
# ---------------------------------------------------------------------------

def _keywords_and_traits(controller, instance_id: str) -> set[str]:
    """敌人关键词+特质（小写）集合。"""
    inst = controller.game_state.get_card_instance(instance_id)
    cd = controller.game_state.get_card_data(inst.card_id) if inst else None
    if cd is None:
        return set()
    out = {str(k).lower() for k in (getattr(cd, "keywords", None) or [])}
    out |= {str(t).lower() for t in (getattr(cd, "traits", None) or [])}
    return out


def _is_staff_enemy(controller, instance_id: str) -> bool:
    return "staff" in _keywords_and_traits(controller, instance_id)


def _is_spider_enemy(controller, instance_id: str) -> bool:
    tokens = _keywords_and_traits(controller, instance_id)
    return "spider" in tokens or "蜘蛛" in tokens


def _is_ancient_one(controller, instance_id: str) -> bool:
    tokens = _keywords_and_traits(controller, instance_id)
    return "ancient_one" in tokens or "ancient one" in tokens or "古神" in tokens


def _is_swarming_enemy(controller, instance_id: str) -> bool:
    tokens = _keywords_and_traits(controller, instance_id)
    if "swarming" in tokens:
        return True
    inst = controller.game_state.get_card_instance(instance_id)
    cd = controller.game_state.get_card_data(inst.card_id) if inst else None
    return bool(cd) and "swarming" in (getattr(cd, "text", "") or "").lower()


def _location_has_trait(controller, location_id: str, *traits: str) -> bool:
    loc = controller.game_state.get_location(location_id)
    if loc is None or loc.card_data is None:
        return False
    have = {str(t).lower() for t in (loc.card_data.traits or [])}
    return any(t.lower() in have for t in traits)


def _target_enemy_id(controller, ctx) -> str | None:
    """本次检定针对的敌人（enemy_id > target > source，取第一个敌人实例）。"""
    for cand in (getattr(ctx, "enemy_id", None),
                 getattr(ctx, "target", None),
                 getattr(ctx, "source", None)):
        if not cand:
            continue
        inst = controller.game_state.get_card_instance(cand)
        cd = controller.game_state.get_card_data(inst.card_id) if inst else None
        if cd is not None and cd.type.value == "enemy":
            return cand
    return None


def _enemy_attacks(controller, instance_id: str, inv) -> bool:
    """敌人立刻攻击：按卡面伤害/恐惧直接加到调查员。"""
    inst = controller.game_state.get_card_instance(instance_id)
    cd = controller.game_state.get_card_data(inst.card_id) if inst else None
    if cd is None:
        return False
    inv.damage += cd.enemy_damage or 0
    inv.horror += cd.enemy_horror or 0
    return True


def _enemy_location(controller, instance_id: str) -> str | None:
    for inv in controller.game_state.investigators.values():
        if instance_id in inv.threat_area:
            return inv.location_id
    for loc in controller.game_state.locations.values():
        if instance_id in loc.enemies:
            return loc.location_id
    return None


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
# TDE 机制状态辅助（均读写 scenario.vars）
# ---------------------------------------------------------------------------

def _infested_count(controller) -> int:
    return len(controller.s.vars.get("infested_locations") or [])


def _make_infestation_test(controller) -> None:
    """侵染检定（简化：独立侵染袋未实现，仅计数）。"""
    s = controller.s
    s.vars["infestation_tests_made"] = int(s.vars.get("infestation_tests_made", 0) or 0) + 1
    s.vars.setdefault("infested_locations", [])


def _signs_of_gods(controller) -> int:
    return int(controller.s.vars.get("signs_of_gods", 0) or 0)


def _alarm(controller, inv_id: str) -> int:
    return int((controller.s.vars.get("alarm_levels") or {}).get(inv_id, 0) or 0)


def _raise_alarm(controller, inv_id: str, n: int = 1) -> None:
    table = controller.s.vars.setdefault("alarm_levels", {})
    table[inv_id] = int(table.get(inv_id, 0) or 0) + n


def _scenario_card_damage(controller) -> int:
    return int(controller.s.vars.get("scenario_card_damage", 0) or 0)


def _add_swarm_card(controller, instance_id: str) -> None:
    table = controller.s.vars.setdefault("swarm_cards", {})
    table[instance_id] = int(table.get(instance_id, 0) or 0) + 1


def _add_shroud_bonus(controller, location_id: str, n: int) -> None:
    table = controller.s.vars.setdefault("shroud_bonus_round", {})
    table[location_id] = int(table.get(location_id, 0) or 0) + n


def _draw_top_encounter_card(controller) -> str | None:
    """抽遭遇牌堆顶（简化：移出牌堆并记录于 vars，不结算其效果）。"""
    s = controller.s
    if not s.encounter_deck:
        return None
    card_id = s.encounter_deck.pop(0)
    s.vars.setdefault("token_drawn_encounters", []).append(card_id)
    return card_id


def _find_unnamable(controller) -> str | None:
    for iid, inst in controller.game_state.cards_in_play.items():
        cd = controller.game_state.get_card_data(inst.card_id)
        if cd is None or cd.type.value != "enemy":
            continue
        if inst.card_id == "the_unnamable" or cd.name == "The Unnamable":
            return iid
    return None


def _ancient_one_at(controller, inv) -> str | None:
    """调查员所在地点（含交战）的古神敌人。"""
    for iid in inv.threat_area:
        if _is_ancient_one(controller, iid):
            return iid
    loc = controller.game_state.get_location(inv.location_id)
    if loc:
        for iid in loc.enemies:
            if _is_ancient_one(controller, iid):
                return iid
    return None


def _attack_profile(controller, instance_id: str) -> int:
    inst = controller.game_state.get_card_instance(instance_id)
    cd = controller.game_state.get_card_data(inst.card_id) if inst else None
    if cd is None:
        return 0
    return (cd.enemy_damage or 0) + (cd.enemy_horror or 0)


def _ready_enemies_near(controller, inv) -> list[str]:
    """所在地点及连接地点的就绪（未横置）未交战敌人。"""
    loc = controller.game_state.get_location(inv.location_id)
    if loc is None:
        return []
    out = []
    for lid in [inv.location_id, *loc.connections]:
        l = controller.game_state.get_location(lid)
        if l is None:
            continue
        for iid in l.enemies:
            inst = controller.game_state.get_card_instance(iid)
            if inst is not None and not inst.exhausted:
                out.append(iid)
    return out


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

def apply_token(controller, ctx, inv, pending, success_pending) -> bool:
    """应用 TDE 剧本的符号标记效果。已处理返回 True，否则 False。"""
    token = ctx.chaos_token
    if token not in _SYMBOL_TOKENS:
        return False
    sid = controller.s.scenario_id
    if sid not in TDE_SCENARIO_IDS or inv is None:
        return False

    hard = controller._is_hard_difficulty
    handler = _SCENARIO_HANDLERS.get(sid)
    if handler is None:
        return False
    handler(controller, ctx, inv, pending, success_pending, hard)

    if ctx.extra.get("token_text"):
        ctx.game_state.log_effect(f"🎲 标记效果：{ctx.extra['token_text']}")
    return True


# ---------------------------------------------------------------------------
# 各剧本效果（front=Easy/Standard，back=Hard/Expert）
# ---------------------------------------------------------------------------

def _btgs(controller, ctx, inv, pending, success_pending, hard) -> None:
    """Beyond the Gates of Sleep 梦境门外。

    本剧本混沌袋无 elder_thing（参考卡两面均未列出），不处理该标记。
    """
    token = ctx.chaos_token
    if token == ChaosTokenType.SKULL:
        hand = len(inv.hand)
        x = hand if hard else -(-hand // 2)  # 标准面：手牌数的一半（向上取整）
        if x:
            ctx.modify_amount(-x, "btgs_skull")
        ctx.extra["token_text"] = (
            f"骷髅 -{x}（{'手牌张数' if hard else '手牌张数的一半(向上取整)'}：{hand}）"
        )
    elif token == ChaosTokenType.CULTIST:
        if hard:
            # 困难面：已揭示的 [[Woods]] 地点（特质匹配）
            x = sum(
                1 for loc in controller.game_state.locations.values()
                if loc.revealed and loc.card_data
                and "woods" in {str(t).lower() for t in (loc.card_data.traits or [])}
            )
            label = "已揭示的Woods地点"
        else:
            # 标准面：已揭示的 Enchanted Woods 地点（卡名/卡 id 匹配）
            x = sum(
                1 for loc in controller.game_state.locations.values()
                if loc.revealed and (
                    loc.location_id.startswith("enchanted_woods")
                    or (loc.card_data and loc.card_data.name == "Enchanted Woods")
                )
            )
            label = "已揭示的魔幻森林地点"
        if x:
            ctx.modify_amount(-x, "btgs_cultist")
        ctx.extra["token_text"] = f"异教徒 -{x}（{label}×{x}）"
    elif token == ChaosTokenType.TABLET:
        ctx.modify_amount(-2, "btgs_tablet")
        target = _target_enemy_id(controller, ctx)
        vs_swarming = (
            ctx.skill_type in (Skill.COMBAT, Skill.AGILITY)
            and target is not None
            and _is_swarming_enemy(controller, target)
        )
        if hard:
            # 困难面无需失败即触发
            if vs_swarming:
                _add_swarm_card(controller, target)
                ctx.extra["token_text"] = "石板 -2，对蜂拥敌人攻击/躲避：其+1蜂群卡（简化：记录于vars）"
            else:
                ctx.extra["token_text"] = "石板 -2"
        else:
            if vs_swarming:
                pending.add("btgs_tablet_swarm")
                ctx.extra["token_text"] = "石板 -2，若失败且为对蜂拥敌人的攻击/躲避：其+1蜂群卡"
            else:
                ctx.extra["token_text"] = "石板 -2"


def _wn(controller, ctx, inv, pending, success_pending, hard) -> None:
    """Waking Nightmare 苏醒梦魇。"""
    token = ctx.chaos_token
    if token == ChaosTokenType.SKULL:
        engaged_staff = any(_is_staff_enemy(controller, iid) for iid in inv.threat_area)
        v = (-4 if engaged_staff else -2) if hard else (-3 if engaged_staff else -1)
        ctx.modify_amount(v, "wn_skull")
        ctx.extra["token_text"] = f"骷髅 {v}" + ("（与Staff敌人交战中）" if engaged_staff else "")
    elif token == ChaosTokenType.CULTIST:
        if hard:
            # 困难面：密谋2/3 时直接进行侵染检定（无需失败）
            ctx.extra["token_text"] = "异教徒 再揭示1个标记"
            if (controller.s.current_agenda_index or 0) in (1, 2):
                _make_infestation_test(controller)
                ctx.extra["token_text"] += "，密谋2/3：进行侵染检定（简化：仅记录）"
        else:
            pending.add("wn_cultist_infestation")
            ctx.extra["token_text"] = (
                "异教徒 再揭示1个标记，若失败且为密谋2/3：进行侵染检定（简化：仅记录）"
            )
        _reveal_extra_token(controller, ctx, "wn_cultist_extra")
    elif token == ChaosTokenType.ELDER_THING:
        n = _infested_count(controller)
        x = n + (1 if hard else 0)
        if x:
            ctx.modify_amount(-x, "wn_elder_thing")
        ctx.extra["token_text"] = f"旧神之物 -{x}（被侵染地点×{n}{'，+1' if hard else ''}）"


def _tsfk(controller, ctx, inv, pending, success_pending, hard) -> None:
    """The Search for Kadath 寻找卡达斯。"""
    token = ctx.chaos_token
    if token == ChaosTokenType.SKULL:
        n = _signs_of_gods(controller)
        x = n + (1 if hard else 0)
        if x:
            ctx.modify_amount(-x, "tsfk_skull")
        ctx.extra["token_text"] = f"骷髅 -{x}（已发现神之印记×{n}{'，+1' if hard else ''}）"
    elif token == ChaosTokenType.CULTIST:
        if ctx.skill_type == Skill.INTELLECT:
            pending.add("tsfk_cultist_shroud_hard" if hard else "tsfk_cultist_shroud")
            ctx.extra["token_text"] = (
                f"异教徒 再揭示1个标记，若失败且为调查：所在地点本轮隐蔽值+{2 if hard else 1}"
            )
        else:
            ctx.extra["token_text"] = "异教徒 再揭示1个标记"
        _reveal_extra_token(controller, ctx, "tsfk_cultist_extra")
    elif token == ChaosTokenType.TABLET:
        ctx.modify_amount(-3 if hard else -2, "tsfk_tablet")
        pending.add("tsfk_tablet_choice")
        ctx.extra["token_text"] = (
            f"石板 {-3 if hard else -2}，若失败：受1伤害1恐惧，或当前密谋+1毁灭（自动选择）"
        )
    elif token == ChaosTokenType.ELDER_THING:
        ctx.modify_amount(1 if hard else 2, "tsfk_elder_thing")
        if ctx.skill_type == Skill.INTELLECT:
            success_pending.add("tsfk_elder_extra_clue")
            ctx.extra["token_text"] = (
                f"旧神之物 {'+1' if hard else '+2'}，黑猫指路：调查成功则额外发现1线索"
            )
        else:
            ctx.extra["token_text"] = f"旧神之物 {'+1' if hard else '+2'}"


def _atsoh(controller, ctx, inv, pending, success_pending, hard) -> None:
    """A Thousand Shapes of Horror 千面恐惧。"""
    token = ctx.chaos_token
    if token == ChaosTokenType.SKULL:
        graveyard = _location_has_trait(controller, inv.location_id, "graveyard", "墓地", "墓園")
        v = (-4 if graveyard else -2) if hard else (-3 if graveyard else -1)
        ctx.modify_amount(v, "atsoh_skull")
        ctx.extra["token_text"] = f"骷髅 {v}" + ("（墓园地点）" if graveyard else "")
    elif token == ChaosTokenType.CULTIST:
        pending.add("atsoh_cultist_unnamable")
        ctx.extra["token_text"] = (
            "异教徒 再揭示1个标记，若失败且无名之物在场：它立刻攻击你"
        )
        _reveal_extra_token(controller, ctx, "atsoh_cultist_extra")
    elif token == ChaosTokenType.TABLET:
        ctx.modify_amount(1 if hard else 2, "atsoh_tablet")
        success_pending.add("atsoh_tablet_evade")
        ctx.extra["token_text"] = (
            f"石板 {'+1' if hard else '+2'}，黑猫引开注意：成功则躲避1个战斗值≤超出值的敌人（自动选择）"
        )
    elif token == ChaosTokenType.ELDER_THING:
        ctx.modify_amount(-3 if hard else -2, "atsoh_elder_thing")
        pending.add("atsoh_elder_choice")
        ctx.extra["token_text"] = (
            f"旧神之物 {-3 if hard else -2}，若失败：将你的1个线索放到所在地点，或受1伤害（自动选择）"
        )


def _dsom(controller, ctx, inv, pending, success_pending, hard) -> None:
    """Dark Side of the Moon 月之暗面。"""
    token = ctx.chaos_token
    if token == ChaosTokenType.SKULL:
        alarm = _alarm(controller, inv.investigator_id)
        x = alarm if hard else -(-alarm // 2)  # 标准面：警报等级的一半（向上取整）
        if x:
            ctx.modify_amount(-x, "dsom_skull")
        ctx.extra["token_text"] = (
            f"骷髅 -{x}（{'警报等级' if hard else '警报等级的一半(向上取整)'}：{alarm}）"
        )
    elif token == ChaosTokenType.CULTIST:
        pending.add("dsom_cultist_encounter")
        ctx.extra["token_text"] = (
            "异教徒 再揭示1个标记，若失败且警报等级高于修正后技能值："
            "检定结束后抽遭遇牌堆顶（简化：不结算）"
        )
        _reveal_extra_token(controller, ctx, "dsom_cultist_extra")
    elif token == ChaosTokenType.TABLET:
        ctx.modify_amount(-2 if hard else -1, "dsom_tablet")
        pending.add("dsom_tablet_alarm")
        ctx.extra["token_text"] = f"石板 {-2 if hard else -1}，若失败：警报等级+1"
    elif token == ChaosTokenType.ELDER_THING:
        ctx.modify_amount(0 if hard else 1, "dsom_elder_thing")
        if ctx.skill_type == Skill.AGILITY:
            success_pending.add("dsom_elder_evade_damage")
            ctx.extra["token_text"] = (
                f"旧神之物 {0 if hard else '+1'}，黑猫召唤猫群：躲避成功则对被躲避敌人造成2伤害"
            )
        else:
            ctx.extra["token_text"] = f"旧神之物 {0 if hard else '+1'}"


def _ponr(controller, ctx, inv, pending, success_pending, hard) -> None:
    """Point of No Return 不归点。"""
    token = ctx.chaos_token
    if token == ChaosTokenType.SKULL:
        dmg = _scenario_card_damage(controller)
        x = dmg + (1 if hard else 0)
        if x:
            ctx.modify_amount(-x, "ponr_skull")
        ctx.extra["token_text"] = f"骷髅 -{x}（本卡上的伤害×{dmg}{'，+1' if hard else ''}）"
    elif token == ChaosTokenType.CULTIST:
        pending.add("ponr_cultist_encounter")
        ctx.extra["token_text"] = (
            "异教徒 再揭示1个标记，若失败：检定结束后抽遭遇牌堆顶（简化：不结算）"
        )
        _reveal_extra_token(controller, ctx, "ponr_cultist_extra")
    elif token == ChaosTokenType.TABLET:
        ctx.modify_amount(0 if hard else 1, "ponr_tablet")
        if ctx.skill_type == Skill.INTELLECT:
            success_pending.add("ponr_tablet_draw")
            ctx.extra["token_text"] = (
                f"石板 {0 if hard else '+1'}，黑猫引路穿越死火：调查成功则抽1张牌"
            )
        else:
            ctx.extra["token_text"] = f"石板 {0 if hard else '+1'}"
    elif token == ChaosTokenType.ELDER_THING:
        ctx.modify_amount(-4 if hard else -3, "ponr_elder_thing")
        pending.add("ponr_elder_enemy_attack")
        ctx.extra["token_text"] = (
            f"旧神之物 {-4 if hard else -3}，若失败2点及以上：所在/连接地点1个就绪敌人"
            "移至你处、与你交战并立刻攻击（自动选最弱）"
        )


def _wgd(controller, ctx, inv, pending, success_pending, hard) -> None:
    """Where the Gods Dwell 众神栖所。"""
    token = ctx.chaos_token
    if token == ChaosTokenType.SKULL:
        act_no = (controller.s.current_act_index or 0) + 1
        agenda_no = (controller.s.current_agenda_index or 0) + 1
        x = act_no + agenda_no if hard else act_no
        ctx.modify_amount(-x, "wgd_skull")
        ctx.extra["token_text"] = (
            f"骷髅 -{x}（当前剧情编号{act_no}" + (f"+当前密谋编号{agenda_no}" if hard else "") + "）"
        )
    elif token == ChaosTokenType.CULTIST:
        pending.add("wgd_cultist_doom")
        ctx.extra["token_text"] = (
            "异教徒 再揭示1个标记，若失败：当前密谋+1毁灭（可能推进密谋）"
        )
        _reveal_extra_token(controller, ctx, "wgd_cultist_extra")
    elif token == ChaosTokenType.TABLET:
        ctx.modify_amount(-6 if hard else -4, "wgd_tablet")
        pending.add("wgd_tablet_nyarlathotep")
        ctx.extra["token_text"] = (
            f"石板 {-6 if hard else -4}，若失败：揭示手牌中1只奈亚拉托提普，"
            "它攻击你并洗入遭遇牌堆"
        )
    elif token == ChaosTokenType.ELDER_THING:
        ctx.modify_amount(-1 if hard else 0, "wgd_elder_thing")
        ctx.extra["token_text"] = f"旧神之物 {-1 if hard else 0}（黑猫提醒你这只是一场梦）"


def _wotc(controller, ctx, inv, pending, success_pending, hard) -> None:
    """Weaver of the Cosmos 宇宙织者。"""
    token = ctx.chaos_token
    if token == ChaosTokenType.SKULL:
        dooms = [loc.doom for loc in controller.game_state.locations.values()]
        x = sum(dooms) if hard else (max(dooms) if dooms else 0)
        if x:
            ctx.modify_amount(-x, "wotc_skull")
        ctx.extra["token_text"] = (
            f"骷髅 -{x}（{'场上地点毁灭总数' if hard else '地点毁灭最大值'}：{x}）"
        )
    elif token == ChaosTokenType.CULTIST:
        pending.add("wotc_cultist_ao_attack")
        ctx.extra["token_text"] = (
            "异教徒 再揭示1个标记，若失败且你所在地点有古神敌人：它立刻攻击你"
        )
        _reveal_extra_token(controller, ctx, "wotc_cultist_extra")
    elif token == ChaosTokenType.TABLET:
        ctx.modify_amount(-1 if hard else 0, "wotc_tablet")
        success_pending.add("wotc_tablet_remove_doom")
        ctx.extra["token_text"] = (
            f"石板 {-1 if hard else 0}，黑猫撕扯巨网：成功2点及以上则所在地点-1毁灭"
        )
    elif token == ChaosTokenType.ELDER_THING:
        ctx.modify_amount(-4 if hard else -3, "wotc_elder_thing")
        pending.add("wotc_elder_spider_doom")
        ctx.extra["token_text"] = (
            f"旧神之物 {-4 if hard else -3}，若攻击蜘蛛敌人失败：其所在地点+1毁灭"
        )


_SCENARIO_HANDLERS = {
    "beyond_the_gates_of_sleep": _btgs,
    "waking_nightmare": _wn,
    "the_search_for_kadath": _tsfk,
    "a_thousand_shapes_of_horror": _atsoh,
    "dark_side_of_the_moon": _dsom,
    "point_of_no_return": _ponr,
    "where_gods_dwell": _wgd,
    "weaver_of_the_cosmos": _wotc,
}


# ---------------------------------------------------------------------------
# 失败/成功结算
# ---------------------------------------------------------------------------

def on_fail(controller, ctx, pending) -> None:
    """SKILL_TEST_FAILED 时结算 TDE token 的条件效果。"""
    if not pending:
        return
    inv = ctx.game_state.get_investigator(ctx.investigator_id)
    if inv is None:
        return
    log = ctx.game_state.log_effect

    # --- Beyond the Gates of Sleep ---
    if "btgs_tablet_swarm" in pending:
        target = _target_enemy_id(controller, ctx)
        if target is not None and _is_swarming_enemy(controller, target):
            _add_swarm_card(controller, target)
            log("💀 石板失败效果：蜂拥敌人+1蜂群卡（简化：记录于vars）")
        pending.discard("btgs_tablet_swarm")

    # --- Waking Nightmare ---
    if "wn_cultist_infestation" in pending:
        if (controller.s.current_agenda_index or 0) in (1, 2):
            _make_infestation_test(controller)
            log("💀 异教徒失败效果：密谋2/3，进行侵染检定（简化：侵染袋未实现，仅记录）")
        pending.discard("wn_cultist_infestation")

    # --- The Search for Kadath ---
    if "tsfk_cultist_shroud" in pending:
        _add_shroud_bonus(controller, inv.location_id, 1)
        log("💀 异教徒失败效果：所在地点本轮隐蔽值+1（记录于vars）")
        pending.discard("tsfk_cultist_shroud")
    if "tsfk_cultist_shroud_hard" in pending:
        _add_shroud_bonus(controller, inv.location_id, 2)
        log("💀 异教徒失败效果：所在地点本轮隐蔽值+2（记录于vars）")
        pending.discard("tsfk_cultist_shroud_hard")
    if "tsfk_tablet_choice" in pending:
        # 简化：自动取最有利——不致败则受1伤害1恐惧，否则当前密谋+1毁灭
        if inv.remaining_health > 1 and inv.remaining_sanity > 1:
            inv.damage += 1
            inv.horror += 1
            log("💀 石板失败效果：受1伤害1恐惧（自动选择）")
        else:
            ctx.game_state.scenario.doom_on_agenda += 1
            controller._check_agenda_threshold()
            log("💀 石板失败效果：当前密谋+1毁灭（自动选择，避免致败）")
        pending.discard("tsfk_tablet_choice")

    # --- A Thousand Shapes of Horror ---
    if "atsoh_cultist_unnamable" in pending:
        iid = _find_unnamable(controller)
        if iid is not None and _enemy_attacks(controller, iid, inv):
            log("💀 异教徒失败效果：无名之物无视距离立刻攻击你")
        pending.discard("atsoh_cultist_unnamable")
    if "atsoh_elder_choice" in pending:
        # 简化：自动取最有利——受伤不致败则受1伤害，否则放1个线索到所在地点
        if inv.remaining_health > 1 or inv.clues <= 0:
            inv.damage += 1
            log("💀 旧神之物失败效果：受1伤害（自动选择）")
        else:
            inv.clues -= 1
            loc = ctx.game_state.get_location(inv.location_id)
            if loc is not None:
                loc.clues += 1
            log("💀 旧神之物失败效果：将你的1个线索放到所在地点（自动选择，避免致败）")
        pending.discard("atsoh_elder_choice")

    # --- Dark Side of the Moon ---
    if "dsom_cultist_encounter" in pending:
        if _alarm(controller, inv.investigator_id) > (ctx.modified_skill or 0):
            card_id = _draw_top_encounter_card(controller)
            if card_id:
                log(f"💀 异教徒失败效果：警报等级高于修正后技能值，抽遭遇牌堆顶《{card_id}》（简化：未结算）")
        pending.discard("dsom_cultist_encounter")
    if "dsom_tablet_alarm" in pending:
        _raise_alarm(controller, inv.investigator_id, 1)
        log("💀 石板失败效果：警报等级+1")
        pending.discard("dsom_tablet_alarm")

    # --- Point of No Return ---
    if "ponr_cultist_encounter" in pending:
        card_id = _draw_top_encounter_card(controller)
        if card_id:
            log(f"💀 异教徒失败效果：抽遭遇牌堆顶《{card_id}》（简化：未结算）")
        pending.discard("ponr_cultist_encounter")
    if "ponr_elder_enemy_attack" in pending:
        margin = (ctx.difficulty or 0) - (ctx.modified_skill or 0)
        if margin >= 2:
            candidates = _ready_enemies_near(controller, inv)
            if candidates:
                target = min(candidates, key=lambda iid: _attack_profile(controller, iid))
                _engage_investigator(controller, target, inv)
                _enemy_attacks(controller, target, inv)
                log("💀 旧神之物失败效果：就绪敌人移至你所在地点、与你交战并立刻攻击（自动选最弱）")
        pending.discard("ponr_elder_enemy_attack")

    # --- Where the Gods Dwell ---
    if "wgd_cultist_doom" in pending:
        ctx.game_state.scenario.doom_on_agenda += 1
        controller._check_agenda_threshold()
        log("💀 异教徒失败效果：当前密谋+1毁灭")
        pending.discard("wgd_cultist_doom")
    if "wgd_tablet_nyarlathotep" in pending:
        card_id = next(
            (cid for cid in inv.hand
             if "nyarlathotep" in str(cid).lower()
             or (lambda cd: cd is not None and cd.name == "Nyarlathotep")(
                 ctx.game_state.get_card_data(cid))),
            None,
        )
        if card_id is not None:
            inv.hand.remove(card_id)
            cd = ctx.game_state.get_card_data(card_id)
            if cd is not None:
                inv.damage += cd.enemy_damage or 0
                inv.horror += cd.enemy_horror or 0
            ctx.game_state.scenario.encounter_deck.append(card_id)
            random.shuffle(ctx.game_state.scenario.encounter_deck)
            log("💀 石板失败效果：揭示手牌中的奈亚拉托提普，它攻击你并洗入遭遇牌堆")
        pending.discard("wgd_tablet_nyarlathotep")

    # --- Weaver of the Cosmos ---
    if "wotc_cultist_ao_attack" in pending:
        iid = _ancient_one_at(controller, inv)
        if iid is not None and _enemy_attacks(controller, iid, inv):
            log("💀 异教徒失败效果：你所在地点的古神敌人立刻攻击你")
        pending.discard("wotc_cultist_ao_attack")
    if "wotc_elder_spider_doom" in pending:
        if ctx.skill_type == Skill.COMBAT:
            target = _target_enemy_id(controller, ctx)
            if target is not None and _is_spider_enemy(controller, target):
                loc_id = _enemy_location(controller, target) or inv.location_id
                loc = ctx.game_state.get_location(loc_id)
                if loc is not None:
                    loc.doom += 1
                    log("💀 旧神之物失败效果：攻击蜘蛛敌人失败，其所在地点+1毁灭")
        pending.discard("wotc_elder_spider_doom")


def on_success(controller, ctx, pending) -> None:
    """SKILL_TEST_SUCCESSFUL 时结算 TDE token 的条件效果。"""
    if not pending:
        return
    inv = ctx.game_state.get_investigator(ctx.investigator_id)
    if inv is None:
        return
    log = ctx.game_state.log_effect

    # --- The Search for Kadath ---
    if "tsfk_elder_extra_clue" in pending:
        loc = ctx.game_state.get_location(inv.location_id)
        if loc is not None and loc.clues > 0:
            loc.clues -= 1
            inv.clues += 1
            log("🎲 旧神之物成功效果：黑猫指路，额外发现1个线索")
        pending.discard("tsfk_elder_extra_clue")

    # --- A Thousand Shapes of Horror ---
    if "atsoh_tablet_evade" in pending:
        margin = (ctx.modified_skill or 0) - (ctx.difficulty or 0)
        # 简化：自动选战斗值最高且 ≤ 成功超出值的敌人
        best = None  # (fight, instance_id)
        for iid, inst in ctx.game_state.cards_in_play.items():
            cd = ctx.game_state.get_card_data(inst.card_id)
            if cd is None or cd.type.value != "enemy":
                continue
            fight = cd.enemy_fight or 0
            if fight <= margin and (best is None or fight > best[0]):
                best = (fight, iid)
        if best is not None:
            iid = best[1]
            inst = ctx.game_state.get_card_instance(iid)
            if inst is not None:
                inst.exhausted = True
            for other in ctx.game_state.investigators.values():
                if iid in other.threat_area:
                    other.threat_area.remove(iid)
            cd = ctx.game_state.get_card_data(inst.card_id) if inst else None
            log(f"🎲 石板成功效果：黑猫引开注意，躲避《{cd.name_cn if cd else iid}》（自动选最高战斗值）")
        pending.discard("atsoh_tablet_evade")

    # --- Dark Side of the Moon ---
    if "dsom_elder_evade_damage" in pending:
        target = _target_enemy_id(controller, ctx)
        if target is not None:
            controller.game.damage_engine.deal_damage_to_enemy(
                target, 2, investigator_id=inv.investigator_id,
            )
            log("🎲 旧神之物成功效果：黑猫召唤猫群，对被躲避的敌人造成2伤害")
        pending.discard("dsom_elder_evade_damage")

    # --- Point of No Return ---
    if "ponr_tablet_draw" in pending:
        if inv.deck:
            inv.hand.append(inv.deck.pop(0))
            log("🎲 石板成功效果：黑猫引路穿越死火，抽1张牌")
        pending.discard("ponr_tablet_draw")

    # --- Weaver of the Cosmos ---
    if "wotc_tablet_remove_doom" in pending:
        margin = (ctx.modified_skill or 0) - (ctx.difficulty or 0)
        loc = ctx.game_state.get_location(inv.location_id)
        if margin >= 2 and loc is not None and loc.doom > 0:
            loc.doom -= 1
            log("🎲 石板成功效果：黑猫撕扯巨网，所在地点-1毁灭")
        pending.discard("wotc_tablet_remove_doom")
