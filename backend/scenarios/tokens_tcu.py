"""万象祭环 (The Circle Undone, TCU) 8 剧本的符号混沌标记效果。

效果文本以卡面英文为准（data/encounter_cards/the_circle_undone.json 中
type=scenario 的卡）：简单/普通取正面 text，困难/专家取背面 back_text；
结构化参考 .tools/arkham-cards-data/chaos_tokens.json（与卡面一致）。

接线方式（由主代理统一接入 official_core._scenario_token_effects 等三处）：

    from backend.scenarios import tokens_tcu
    # CHAOS_TOKEN_RESOLVED：
    if tokens_tcu.apply_token(self, ctx, inv, pending, success_pending):
        if ctx.extra.get("token_text"):
            ctx.game_state.log_effect(f"🎲 标记效果：{ctx.extra['token_text']}")
    # SKILL_TEST_FAILED：tokens_tcu.on_fail(self, ctx, pending)
    # SKILL_TEST_SUCCESSFUL：tokens_tcu.on_success(self, ctx, pending)

TCU 特有机制与简化（选择类分支一律自动取对玩家最有利，逐处注明）：
- 闹鬼（haunted）：引擎无 Haunted 能力实现，以
  scenario.vars["haunted_locations"]（地点 id 集合）标记闹鬼地点；
  “结算所在地点的所有闹鬼能力”简化为日志 + vars["haunted_abilities_resolved"] 计数。
- 关键词：TCU 数据库 traits 直接存英文（"witch"/"spectral"/"cultist"），而
  official_core._TRAIT_TO_KEYWORD 只有中文映射（缺 "女巫"→witch、"異端"→heretic、
  "幽靈"→spectral），故本模块的关键词判定同时检查 keywords 与 traits（中英均可）。
- circle 行动：引擎没有 circle 行动，以 ctx.extra["circle_action"] 为判定钩子。
- 未了之事（Unfinished Business）：victory_display 中 card_id 为
  "unfinished_business" 或以 "heretic_" 开头的卡；其“回合结束”强制能力未实现，
  触发简化为日志 + vars["wos_ub_forced_triggered"] 计数。
- 破口（breach，in_the_clutches_of_chaos）：以 scenario.vars["breaches"]
  （{location_id: 数量}）与 vars["act_breaches"]（当前场景上的破口）计数。
- “若你本次检定的修正技能值为 0”（before_the_black_throne 旧神之物）：引擎在
  CHAOS_TOKEN_RESOLVED 时ctx尚未写入 modified_skill，回退用调查员基础技能值
  （不含投入卡牌/修正），代码处注明。
- 失败结算时“再揭示 1 个标记”（ftgg 困难面）：检定结果已判定，额外标记不影响
  结果，简化为日志。
"""

from __future__ import annotations

import math
import random
from typing import Any

TCU_SCENARIO_IDS = {
    "the_witching_hour",
    "at_deaths_doorstep",
    "the_secret_name",
    "the_wages_of_sin",
    "for_the_greater_good",
    "union_and_disillusion",
    "in_the_clutches_of_chaos",
    "before_the_black_throne",
}

# 关键词候选名（英文 keyword/trait + 中文 trait），TCU 数据 traits 为英文。
_WITCH = ("witch", "女巫")
_CULTIST = ("cultist", "異教徒", "异教徒")
_SPECTRAL = ("spectral", "幽靈", "幽灵", "靈體")
_EXTRADIMENSIONAL = ("extradimensional", "異次元", "异次元")


# ---------------------------------------------------------------------------
# 通用辅助
# ---------------------------------------------------------------------------

def _matches(cd: Any, names: tuple[str, ...]) -> bool:
    """卡牌数据是否含任一关键词（keywords 或 traits，中英均可）。"""
    if cd is None:
        return False
    hay = {str(t).lower() for t in (getattr(cd, "keywords", None) or [])}
    hay |= {str(t).lower() for t in (getattr(cd, "traits", None) or [])}
    return any(n.lower() in hay for n in names)


def _iter_enemies(controller):
    """yield (instance_id, instance, card_data) for each enemy in play."""
    for iid, inst in controller.game_state.cards_in_play.items():
        cd = controller.game_state.get_card_data(inst.card_id)
        if cd is not None and cd.type.value == "enemy":
            yield iid, inst, cd


def _enemies_matching(controller, names: tuple[str, ...]) -> list[str]:
    return [iid for iid, _inst, cd in _iter_enemies(controller) if _matches(cd, names)]


def _enemy_at_location(controller, iid: str, location_id: str) -> bool:
    """敌人是否在某地点（含与该地点调查员交战）。"""
    loc = controller.game_state.get_location(location_id)
    if loc is not None and iid in loc.enemies:
        return True
    for inv in controller.game_state.investigators.values():
        if inv.location_id == location_id and iid in inv.threat_area:
            return True
    return False


def _nearest_enemy_matching(controller, inv, names: tuple[str, ...]) -> str | None:
    """最近的匹配敌人：交战 > 同地点 > 任意（同 official_core._nearest_enemy_with）。"""
    for iid in inv.threat_area:
        inst = controller.game_state.get_card_instance(iid)
        cd = controller.game_state.get_card_data(inst.card_id) if inst else None
        if _matches(cd, names):
            return iid
    loc = controller.game_state.get_location(inv.location_id)
    if loc is not None:
        for iid in loc.enemies:
            inst = controller.game_state.get_card_instance(iid)
            cd = controller.game_state.get_card_data(inst.card_id) if inst else None
            if _matches(cd, names):
                return iid
    for iid, _inst, cd in _iter_enemies(controller):
        if _matches(cd, names):
            return iid
    return None


def _find_instance_by_card_id(controller, card_id: str) -> str | None:
    for iid, inst in controller.game_state.cards_in_play.items():
        if inst.card_id == card_id:
            return iid
    return None


def _location_has_any_trait(controller, location_id: str, names: tuple[str, ...]) -> bool:
    loc = controller.game_state.get_location(location_id)
    if loc is None or loc.card_data is None:
        return False
    traits = {str(t).lower() for t in (loc.card_data.traits or [])}
    return any(n.lower() in traits for n in names)


def _is_haunted(controller, location_id: str) -> bool:
    """闹鬼地点：scenario.vars["haunted_locations"] 集合标记（简化）。"""
    return location_id in set(controller.s.vars.get("haunted_locations") or [])


def _resolve_haunted_abilities(controller, ctx, location_id: str) -> bool:
    """结算所在地点的所有闹鬼能力（简化：仅记录日志与计数）。"""
    if not _is_haunted(controller, location_id):
        return False
    loc = controller.game_state.get_location(location_id)
    name = ""
    if loc is not None and loc.card_data is not None:
        name = loc.card_data.name_cn or loc.card_data.name or location_id
    controller.s.vars["haunted_abilities_resolved"] = \
        int(controller.s.vars.get("haunted_abilities_resolved", 0) or 0) + 1
    ctx.game_state.log_effect(f"👻 结算【{name}】的闹鬼能力（简化：仅记录日志）")
    return True


def _is_attack_or_evasion(ctx) -> bool:
    """攻击/躲避尝试（简化：以战斗/敏捷检定近似，引擎此时 ctx 不带 action）。"""
    return ctx.skill_type is not None and ctx.skill_type.value in ("combat", "agility")


def _enemy_attacks(controller, ctx, inv, iid: str, label: str) -> None:
    """敌人立刻攻击调查员（直接结算伤害/恐惧，参照 tmm_tablet_hard 先例）。"""
    inst = controller.game_state.get_card_instance(iid)
    cd = controller.game_state.get_card_data(inst.card_id) if inst else None
    if cd is None:
        return
    inv.damage += cd.enemy_damage or 0
    inv.horror += cd.enemy_horror or 0
    ctx.game_state.log_effect(
        f"⚔️ {label}：《{cd.name_cn or cd.name}》立刻攻击你"
        f"（{cd.enemy_damage or 0}伤害/{cd.enemy_horror or 0}恐惧）"
    )


def _discard_encounter_top(controller, n: int) -> list[str]:
    """弃遭遇牌堆顶 n 张（顶 = 列表索引 0），返回被弃的卡。"""
    s = controller.s
    out = []
    for _ in range(min(n, len(s.encounter_deck))):
        out.append(s.encounter_deck.pop(0))
    s.encounter_discard.extend(out)
    return out


def _fail_margin(ctx) -> int:
    return max(0, (ctx.difficulty or 0) - (ctx.modified_skill or 0))


def _unfinished_business_count(controller) -> int:
    """胜利牌区中「未了之事」的数量（Heretic 敌人的另一面）。"""
    return sum(
        1 for cid in controller.s.victory_display
        if cid == "unfinished_business" or cid.startswith("heretic_")
    )


def _breaches(controller) -> dict:
    return controller.s.vars.setdefault("breaches", {})


def _azathoth_iid(controller) -> str | None:
    return _find_instance_by_card_id(controller, "azathoth")


def _pull_enemy_matching(controller, names: tuple[str, ...]) -> str | None:
    """从遭遇牌堆、弃牌堆搜寻匹配敌人（同 _pull_enemy_by_keyword，但兼容 traits）。"""
    s = controller.s
    for pile_name in ("encounter_deck", "encounter_discard"):
        pile = getattr(s, pile_name)
        for card_id in list(pile):
            cd = controller.game_state.get_card_data(card_id)
            if cd is not None and cd.type.value == "enemy" and _matches(cd, names):
                pile.remove(card_id)
                return card_id
    return None


def _draw_bottommost_treachery(controller, ctx) -> None:
    """抽取遭遇弃牌堆最底下的诡计（底 = 列表索引 0）并结算。"""
    s = controller.s
    for card_id in list(s.encounter_discard):
        cd = controller.game_state.get_card_data(card_id)
        if cd is not None and cd.type.value == "treachery":
            s.encounter_discard.remove(card_id)
            ctx.game_state.log_effect(
                f"🀄 石板失败效果：抽到遭遇弃牌堆底的诡计《{cd.name_cn or cd.name}》"
            )
            controller.resolve_encounter_card(
                card_id, investigator_id=ctx.investigator_id or "player"
            )
            return
    ctx.game_state.log_effect("🀄 石板失败效果：遭遇弃牌堆中没有诡计")


def _resolve_all_hunters(controller, ctx) -> None:
    """结算场上每个敌人的猎手关键词（复用敌方阶段的猎手移动实现）。"""
    controller.game.enemy_phase._resolve_hunter_movement()
    ctx.game_state.log_effect("🏹 结算场上每个敌人的猎手关键词")


def _witches_near(controller, inv, *, require_exhausted_or_damaged: bool) -> list[str]:
    """你所在地点及相连地点的女巫敌人。"""
    loc = controller.game_state.get_location(inv.location_id)
    loc_ids = [inv.location_id] + list(loc.connections if loc else [])
    out = []
    for iid, inst, cd in _iter_enemies(controller):
        if not _matches(cd, _WITCH):
            continue
        if require_exhausted_or_damaged and not (inst.exhausted or inst.damage > 0):
            continue
        if any(_enemy_at_location(controller, iid, lid) for lid in loc_ids):
            out.append(iid)
    return out


def _ready_and_heal(controller, iid: str) -> None:
    inst = controller.game_state.get_card_instance(iid)
    if inst is not None:
        inst.exhausted = False
        inst.damage = 0


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

def apply_token(controller, ctx, inv, pending, success_pending) -> bool:
    """应用 TCU 剧本的符号标记效果。返回本模块是否认领了该剧本。

    非 TCU 剧本返回 False；TCU 剧本即使抽到非符号标记也返回 True（无效果）。
    """
    from backend.models.enums import ChaosTokenType

    sid = controller.s.scenario_id
    if sid not in TCU_SCENARIO_IDS:
        return False
    token = ctx.chaos_token
    if token not in (ChaosTokenType.SKULL, ChaosTokenType.CULTIST,
                     ChaosTokenType.TABLET, ChaosTokenType.ELDER_THING):
        return True
    handler = _EFFECTS[sid]
    handler(controller, ctx, inv, pending, success_pending, token,
            controller._is_hard_difficulty)
    return True


# ---------------------------------------------------------------------------
# 各剧本效果（hard=True 取困难/专家面）
# ---------------------------------------------------------------------------

def _the_witching_hour(controller, ctx, inv, pending, _sp, token, hard) -> None:
    from backend.models.enums import ChaosTokenType

    if token == ChaosTokenType.SKULL:
        if hard:
            ctx.modify_amount(-2, "twh_skull_hard")
            n = ctx.difficulty or 0
            discarded = _discard_encounter_top(controller, n)
            ctx.extra["token_text"] = f"骷髅 -2，弃遭遇牌堆顶{n}张（本次检定难度）"
            if discarded:
                ctx.game_state.log_effect(f"💀 骷髅效果：弃遭遇牌堆顶{len(discarded)}张")
        else:
            ctx.modify_amount(-1, "twh_skull")
            pending.add("twh_skull_margin_discard")
            ctx.extra["token_text"] = "骷髅 -1，若失败：每差1点弃遭遇牌堆顶1张"
    elif token == ChaosTokenType.TABLET:
        ctx.modify_amount(-2 if hard else -1, "twh_tablet")
        pending.add("twh_tablet_bottom_treachery")
        ctx.extra["token_text"] = f"石板 {-2 if hard else -1}，若失败：抽遭遇弃牌堆最底下的诡计"
    elif token == ChaosTokenType.ELDER_THING:
        ctx.modify_amount(-4 if hard else -3, "twh_elder_thing")
        if hard:
            pending.add("twh_elder_witches_all")
            ctx.extra["token_text"] = "旧神之物 -4，若失败：准备并治愈你所在地及相连地点的每个女巫敌人"
        else:
            pending.add("twh_elder_witch_one")
            ctx.extra["token_text"] = "旧神之物 -3，若失败：准备并治愈你所在地或相连地点的1个女巫敌人（自动选伤害最低者）"


def _at_deaths_doorstep(controller, ctx, inv, pending, _sp, token, hard) -> None:
    from backend.models.enums import ChaosTokenType

    if token == ChaosTokenType.SKULL:
        haunted = _is_haunted(controller, inv.location_id)
        x = (4 if haunted else 2) if hard else (3 if haunted else 1)
        ctx.modify_amount(-x, "add_skull")
        ctx.extra["token_text"] = f"骷髅 -{x}" + ("（所在地闹鬼）" if haunted else "")
    elif token == ChaosTokenType.TABLET:
        ctx.modify_amount(-3 if hard else -2, "add_tablet")
        if _is_attack_or_evasion(ctx):
            if hard:
                ctx.extra["token_text"] = "石板 -3，攻击/躲避尝试：结算所在地的闹鬼能力"
                _resolve_haunted_abilities(controller, ctx, inv.location_id)
            else:
                pending.add("add_tablet_haunted")
                ctx.extra["token_text"] = "石板 -2，若失败（攻击/躲避尝试）：结算所在地的闹鬼能力"
        else:
            ctx.extra["token_text"] = f"石板 {-3 if hard else -2}"
    elif token == ChaosTokenType.ELDER_THING:
        ctx.modify_amount(-4 if hard else -2, "add_elder_thing")
        spectral = [iid for iid in _enemies_matching(controller, _SPECTRAL)
                    if _enemy_at_location(controller, iid, inv.location_id)]
        if spectral:
            inv.damage += 1
            if hard:
                inv.horror += 1
            ctx.extra["token_text"] = (
                f"旧神之物 {-4 if hard else -2}，所在地有幽灵敌人：受1伤害"
                + ("1恐惧" if hard else "")
            )
        else:
            ctx.extra["token_text"] = f"旧神之物 {-4 if hard else -2}"


def _the_secret_name(controller, ctx, inv, pending, _sp, token, hard) -> None:
    from backend.models.enums import ChaosTokenType

    if token == ChaosTokenType.SKULL:
        extra_dim = _location_has_any_trait(controller, inv.location_id, _EXTRADIMENSIONAL)
        x = (4 if extra_dim else 2) if hard else (3 if extra_dim else 1)
        ctx.modify_amount(-x, "tsn_skull")
        ctx.extra["token_text"] = f"骷髅 -{x}" + ("（異次元地点）" if extra_dim else "")
    elif token == ChaosTokenType.CULTIST:
        pending.add("tsn_cultist_discard5" if hard else "tsn_cultist_discard3")
        ctx.extra["token_text"] = f"异教徒 再揭示1个标记，若失败：弃遭遇牌堆顶{5 if hard else 3}张"
        controller._reveal_extra_numeric_token(ctx, "tsn_cultist_extra")
    elif token == ChaosTokenType.TABLET:
        ctx.modify_amount(-3 if hard else -2, "tsn_tablet")
        pending.add("tsn_tablet_nahab")
        where = "在场（不论地点）" if hard else "在你所在地"
        ctx.extra["token_text"] = f"石板 {-3 if hard else -2}，若失败且娜哈布{where}：她立刻攻击你"
    elif token == ChaosTokenType.ELDER_THING:
        ctx.modify_amount(-4 if hard else -3, "tsn_elder_thing")
        if hard:
            ctx.extra["token_text"] = "旧神之物 -4，结算场上每个敌人的猎手关键词"
            _resolve_all_hunters(controller, ctx)
        else:
            pending.add("tsn_elder_hunter")
            ctx.extra["token_text"] = "旧神之物 -3，若失败：结算场上每个敌人的猎手关键词"


def _the_wages_of_sin(controller, ctx, inv, pending, _sp, token, hard) -> None:
    from backend.models.enums import ChaosTokenType

    if token == ChaosTokenType.SKULL:
        n = _unfinished_business_count(controller)
        if hard:
            ctx.modify_amount(-n, "wos_skull_hard")
            ctx.extra["token_text"] = f"骷髅 -{n}（胜利牌区未了之事×{n}），再揭示1个标记"
            controller._reveal_extra_numeric_token(ctx, "wos_skull_extra")
        else:
            x = n + 1
            ctx.modify_amount(-x, "wos_skull")
            ctx.extra["token_text"] = f"骷髅 -{x}（胜利牌区未了之事×{n}+1）"
    elif token == ChaosTokenType.CULTIST:
        # 简化：異端 +1战斗/+1躲避持续到本轮结束只记录标记与日志，
        # 引擎按卡面数据读取敌人数值，不实际加成。
        ctx.modify_amount(-4 if hard else -3, "wos_cultist")
        controller.s.vars["wos_heretic_buff_round"] = controller.s.round_number
        ctx.extra["token_text"] = (
            f"异教徒 {-4 if hard else -3}，本轮场上每个異端敌人+1战斗/+1躲避"
            "（简化：仅记录，不实际加成）"
        )
    elif token == ChaosTokenType.TABLET:
        ctx.modify_amount(-4 if hard else -3, "wos_tablet")
        pending.add("wos_tablet_unfinished")
        ctx.extra["token_text"] = (
            f"石板 {-4 if hard else -3}，若失败：触发你威胁区1张未了之事的强制能力"
            "（简化：仅记录）"
        )
    elif token == ChaosTokenType.ELDER_THING:
        ctx.modify_amount(-2, "wos_elder_thing")
        if _is_attack_or_evasion(ctx):
            if hard:
                ctx.extra["token_text"] = "旧神之物 -2，攻击/躲避尝试：结算所在地的闹鬼能力"
                _resolve_haunted_abilities(controller, ctx, inv.location_id)
            else:
                pending.add("wos_elder_haunted")
                ctx.extra["token_text"] = "旧神之物 -2，若失败（攻击/躲避尝试）：结算所在地的闹鬼能力"
        else:
            ctx.extra["token_text"] = "旧神之物 -2"


def _for_the_greater_good(controller, ctx, inv, pending, _sp, token, hard) -> None:
    from backend.models.enums import ChaosTokenType

    if token == ChaosTokenType.SKULL:
        cultists = _enemies_matching(controller, _CULTIST)
        dooms = [int(getattr(controller.game_state.get_card_instance(iid), "doom", 0) or 0)
                 for iid in cultists]
        x = sum(dooms) if hard else (max(dooms) if dooms else 0)
        if x:
            ctx.modify_amount(-x, "ftgg_skull")
        ctx.extra["token_text"] = f"骷髅 -{x}（異教徒敌人{'毁灭总数' if hard else '最高毁灭'}×{x}）"
    elif token == ChaosTokenType.CULTIST:
        ctx.modify_amount(-2, "ftgg_cultist")
        ctx.extra["token_text"] = "异教徒 -2，再揭示1个标记"
        controller._reveal_extra_numeric_token(ctx, "ftgg_cultist_extra")
    elif token == ChaosTokenType.TABLET:
        ctx.modify_amount(-3, "ftgg_tablet")
        pending.add("ftgg_tablet_doom")
        if hard:
            ctx.extra["token_text"] = "石板 -3，若失败：每个異教徒敌人+1毁灭（无则再揭示，简化为日志）"
        else:
            ctx.extra["token_text"] = "石板 -3，若失败：最近的異教徒敌人+1毁灭"
    elif token == ChaosTokenType.ELDER_THING:
        ctx.modify_amount(-3, "ftgg_elder_thing")
        pending.add("ftgg_elder_move_doom")
        if hard:
            ctx.extra["token_text"] = "旧神之物 -3，若失败：毁灭最多的異教徒全部毁灭移至当前密谋（无则再揭示，简化为日志）"
        else:
            ctx.extra["token_text"] = "旧神之物 -3，若失败：最近的異教徒敌人移1毁灭到当前密谋"


def _union_and_disillusion(controller, ctx, inv, pending, _sp, token, hard) -> None:
    from backend.models.enums import ChaosTokenType

    circle = bool(ctx.extra.get("circle_action"))  # 简化：引擎无 circle 行动，用 extra 钩子
    if token == ChaosTokenType.SKULL:
        ctx.modify_amount(-3 if hard else -2, "uad_skull")
        if circle:
            ctx.extra["token_text"] = f"骷髅 {-3 if hard else -2}，circle行动：再揭示1个标记"
            controller._reveal_extra_numeric_token(ctx, "uad_skull_extra")
        else:
            ctx.extra["token_text"] = f"骷髅 {-3 if hard else -2}"
    elif token == ChaosTokenType.CULTIST:
        ctx.modify_amount(-4 if hard else -3, "uad_cultist")
        parts = []
        if inv.damage == 0:
            inv.damage += 1
            parts.append("受1伤害")
        if inv.horror == 0:
            inv.horror += 1
            parts.append("受1恐惧")
        ctx.extra["token_text"] = f"异教徒 {-4 if hard else -3}" + ("，" + "，".join(parts) if parts else "")
    elif token == ChaosTokenType.TABLET:
        ctx.modify_amount(-4 if hard else -3, "uad_tablet")
        pending.add("uad_tablet_spectral_attack")
        ctx.extra["token_text"] = f"石板 {-4 if hard else -3}，若失败：所在地的幽灵敌人攻击你（即使已横置）"
    elif token == ChaosTokenType.ELDER_THING:
        ctx.modify_amount(-4 if hard else -3, "uad_elder_thing")
        if circle:
            pending.add("uad_elder_haunted")
            ctx.extra["token_text"] = f"旧神之物 {-4 if hard else -3}，circle行动若失败：结算所在地的闹鬼能力"
        else:
            ctx.extra["token_text"] = f"旧神之物 {-4 if hard else -3}"


def _in_the_clutches_of_chaos(controller, ctx, inv, pending, _sp, token, hard) -> None:
    from backend.models.enums import ChaosTokenType

    if token == ChaosTokenType.SKULL:
        loc = controller.game_state.get_location(inv.location_id)
        doom = (loc.doom if loc else 0)
        breach = int(_breaches(controller).get(inv.location_id, 0) or 0)
        x = doom + breach + (1 if hard else 0)
        if x:
            ctx.modify_amount(-x, "itcc_skull")
        ctx.extra["token_text"] = f"骷髅 -{x}（所在地毁灭{doom}+破口{breach}" + ("，+1" if hard else "") + "）"
    elif token == ChaosTokenType.CULTIST:
        n = int(_breaches(controller).get(inv.location_id, 0) or 0)
        if n < 3:
            _breaches(controller)[inv.location_id] = n + 1
            ctx.extra["token_text"] = f"异教徒 再揭示1个标记，所在地破口+1（现{n + 1}个）"
        else:
            ctx.extra["token_text"] = "异教徒 再揭示1个标记（所在地破口已达3个，不加）"
        controller._reveal_extra_numeric_token(ctx, "itcc_cultist_extra")
    elif token == ChaosTokenType.TABLET:
        ctx.modify_amount(-3 if hard else -2, "itcc_tablet")
        pending.add("itcc_tablet_remove_breach")
        ctx.extra["token_text"] = f"石板 {-3 if hard else -2}，若失败：每差1点从当前场景移除1个破口"
    elif token == ChaosTokenType.ELDER_THING:
        ctx.modify_amount(-4 if hard else -3, "itcc_elder_thing")
        pending.add("itcc_elder_random_breach")
        ctx.extra["token_text"] = f"旧神之物 {-4 if hard else -3}，若失败：随机1个地点+1破口"


def _before_the_black_throne(controller, ctx, inv, pending, _sp, token, hard) -> None:
    from backend.models.enums import ChaosTokenType

    if token == ChaosTokenType.SKULL:
        aza = _azathoth_iid(controller)
        doom = int(getattr(controller.game_state.get_card_instance(aza), "doom", 0) or 0) if aza else 0
        x = max(2, doom) if hard else max(2, math.ceil(doom / 2))
        ctx.modify_amount(-x, "btbt_skull")
        ctx.extra["token_text"] = f"骷髅 -{x}（阿撒托斯毁灭{doom}" + ("，至少2" if x == 2 else "") + "）"
    elif token == ChaosTokenType.CULTIST:
        pending.add("btbt_cultist_pull")
        ctx.extra["token_text"] = "异教徒 再揭示1个标记，若失败：从遭遇牌堆/弃牌堆搜寻并抽取1个異教徒敌人"
        controller._reveal_extra_numeric_token(ctx, "btbt_cultist_extra")
    elif token == ChaosTokenType.TABLET:
        ctx.modify_amount(-3 if hard else -2, "btbt_tablet")
        pending.add("btbt_tablet_azathoth_attack")
        ctx.extra["token_text"] = f"石板 {-3 if hard else -2}，若失败：阿撒托斯立刻攻击你"
    elif token == ChaosTokenType.ELDER_THING:
        ctx.modify_amount(-6 if hard else -4, "btbt_elder_thing")
        # 简化：CHAOS_TOKEN_RESOLVED 时引擎尚未写入 modified_skill，
        # 回退用调查员基础技能值（不含投入卡牌/修正）。
        modified = ctx.modified_skill
        if modified is None:
            modified = inv.get_skill(ctx.skill_type) if ctx.skill_type is not None else 0
        modified = int(modified or 0)
        aza = _azathoth_iid(controller)
        if modified == 0 and aza is not None:
            inst = controller.game_state.get_card_instance(aza)
            inst.doom = int(getattr(inst, "doom", 0) or 0) + 1
            ctx.extra["token_text"] = f"旧神之物 {-6 if hard else -4}，修正技能值为0：阿撒托斯+1毁灭"
        else:
            ctx.extra["token_text"] = f"旧神之物 {-6 if hard else -4}"


_EFFECTS = {
    "the_witching_hour": _the_witching_hour,
    "at_deaths_doorstep": _at_deaths_doorstep,
    "the_secret_name": _the_secret_name,
    "the_wages_of_sin": _the_wages_of_sin,
    "for_the_greater_good": _for_the_greater_good,
    "union_and_disillusion": _union_and_disillusion,
    "in_the_clutches_of_chaos": _in_the_clutches_of_chaos,
    "before_the_black_throne": _before_the_black_throne,
}


# ---------------------------------------------------------------------------
# 失败 / 成功结算（主代理接 SKILL_TEST_FAILED / SKILL_TEST_SUCCESSFUL）
# ---------------------------------------------------------------------------

def on_fail(controller, ctx, pending) -> None:
    """检定失败后的条件效果。pending 为 apply_token 时登记的标记集合。"""
    if not pending:
        return
    inv = ctx.game_state.get_investigator(ctx.investigator_id)
    if inv is None:
        return
    log = ctx.game_state.log_effect

    # --- The Witching Hour ---
    if "twh_skull_margin_discard" in pending:
        margin = _fail_margin(ctx)
        discarded = _discard_encounter_top(controller, margin)
        if discarded:
            log(f"💀 骷髅失败效果：按差额弃遭遇牌堆顶{len(discarded)}张")
        pending.discard("twh_skull_margin_discard")
    if "twh_tablet_bottom_treachery" in pending:
        _draw_bottommost_treachery(controller, ctx)
        pending.discard("twh_tablet_bottom_treachery")
    if "twh_elder_witch_one" in pending:
        # 简化：自动选对玩家最有利（伤害最低）的合格女巫
        witches = _witches_near(controller, inv, require_exhausted_or_damaged=True)
        if witches:
            target = min(witches, key=lambda i: int(
                getattr(controller.game_state.get_card_instance(i), "damage", 0) or 0))
            _ready_and_heal(controller, target)
            cd = controller.game_state.get_card_data(
                controller.game_state.get_card_instance(target).card_id)
            log(f"💀 旧神之物失败效果：准备并治愈女巫《{cd.name_cn if cd else target}》（自动选伤害最低）")
        pending.discard("twh_elder_witch_one")
    if "twh_elder_witches_all" in pending:
        witches = _witches_near(controller, inv, require_exhausted_or_damaged=False)
        for iid in witches:
            _ready_and_heal(controller, iid)
        if witches:
            log(f"💀 旧神之物失败效果：准备并治愈{len(witches)}个女巫敌人")
        pending.discard("twh_elder_witches_all")

    # --- At Death's Doorstep ---
    if "add_tablet_haunted" in pending:
        _resolve_haunted_abilities(controller, ctx, inv.location_id)
        pending.discard("add_tablet_haunted")

    # --- The Secret Name ---
    if "tsn_cultist_discard3" in pending:
        discarded = _discard_encounter_top(controller, 3)
        if discarded:
            log(f"💀 异教徒失败效果：弃遭遇牌堆顶{len(discarded)}张")
        pending.discard("tsn_cultist_discard3")
    if "tsn_cultist_discard5" in pending:
        discarded = _discard_encounter_top(controller, 5)
        if discarded:
            log(f"💀 异教徒失败效果：弃遭遇牌堆顶{len(discarded)}张")
        pending.discard("tsn_cultist_discard5")
    if "tsn_tablet_nahab" in pending:
        nahab = _find_instance_by_card_id(controller, "nahab")
        if nahab is not None and (
                controller._is_hard_difficulty
                or _enemy_at_location(controller, nahab, inv.location_id)):
            _enemy_attacks(controller, ctx, inv, nahab, "石板失败效果：娜哈布")
        pending.discard("tsn_tablet_nahab")
    if "tsn_elder_hunter" in pending:
        _resolve_all_hunters(controller, ctx)
        pending.discard("tsn_elder_hunter")

    # --- The Wages of Sin ---
    if "wos_tablet_unfinished" in pending:
        ub = next((iid for iid in inv.threat_area
                   if (lambda inst: inst is not None and (
                       inst.card_id == "unfinished_business"
                       or inst.card_id.startswith("heretic_")))(
                       controller.game_state.get_card_instance(iid))), None)
        if ub is not None:
            controller.s.vars["wos_ub_forced_triggered"] = \
                int(controller.s.vars.get("wos_ub_forced_triggered", 0) or 0) + 1
            log("💀 石板失败效果：触发威胁区未了之事的强制能力（简化：仅记录日志）")
        pending.discard("wos_tablet_unfinished")
    if "wos_elder_haunted" in pending:
        _resolve_haunted_abilities(controller, ctx, inv.location_id)
        pending.discard("wos_elder_haunted")

    # --- For the Greater Good ---
    if "ftgg_tablet_doom" in pending:
        cultists = _enemies_matching(controller, _CULTIST)
        if controller._is_hard_difficulty:
            if cultists:
                for iid in cultists:
                    inst = controller.game_state.get_card_instance(iid)
                    inst.doom = int(getattr(inst, "doom", 0) or 0) + 1
                log(f"💀 石板失败效果：{len(cultists)}个異教徒敌人各+1毁灭")
            else:
                # 简化：失败后“再揭示1个标记”不影响已判定的失败，仅记录
                log("💀 石板失败效果：场上无異教徒敌人，再揭示1个标记（简化：仅记录）")
        else:
            target = _nearest_enemy_matching(controller, inv, _CULTIST)
            if target:
                inst = controller.game_state.get_card_instance(target)
                inst.doom = int(getattr(inst, "doom", 0) or 0) + 1
                log("💀 石板失败效果：最近的異教徒敌人+1毁灭")
        pending.discard("ftgg_tablet_doom")
    if "ftgg_elder_move_doom" in pending:
        if controller._is_hard_difficulty:
            cultists = _enemies_matching(controller, _CULTIST)
            doomed = [iid for iid in cultists
                      if int(getattr(controller.game_state.get_card_instance(iid), "doom", 0) or 0) > 0]
            if doomed:
                target = max(doomed, key=lambda i: int(
                    getattr(controller.game_state.get_card_instance(i), "doom", 0) or 0))
                inst = controller.game_state.get_card_instance(target)
                moved = int(getattr(inst, "doom", 0) or 0)
                inst.doom = 0
                controller.s.doom_on_agenda += moved
                controller._check_agenda_threshold()
                log(f"💀 旧神之物失败效果：異教徒的{moved}毁灭移至当前密谋")
            else:
                log("💀 旧神之物失败效果：无带毁灭的異教徒，再揭示1个标记（简化：仅记录）")
        else:
            target = _nearest_enemy_matching(controller, inv, _CULTIST)
            inst = controller.game_state.get_card_instance(target) if target else None
            if inst is not None and int(getattr(inst, "doom", 0) or 0) > 0:
                inst.doom -= 1
                controller.s.doom_on_agenda += 1
                controller._check_agenda_threshold()
                log("💀 旧神之物失败效果：最近異教徒的1毁灭移至当前密谋")
        pending.discard("ftgg_elder_move_doom")

    # --- Union and Disillusion ---
    if "uad_tablet_spectral_attack" in pending:
        spectral = [iid for iid in _enemies_matching(controller, _SPECTRAL)
                    if _enemy_at_location(controller, iid, inv.location_id)]
        if spectral:
            # 简化：自动选对玩家最有利（攻击伤害+恐惧最低）的幽灵敌人
            def _attack_power(iid: str) -> int:
                cd = controller.game_state.get_card_data(
                    controller.game_state.get_card_instance(iid).card_id)
                return (cd.enemy_damage or 0) + (cd.enemy_horror or 0) if cd else 0
            target = min(spectral, key=_attack_power)
            _enemy_attacks(controller, ctx, inv, target, "石板失败效果：幽灵敌人")
        pending.discard("uad_tablet_spectral_attack")
    if "uad_elder_haunted" in pending:
        _resolve_haunted_abilities(controller, ctx, inv.location_id)
        pending.discard("uad_elder_haunted")

    # --- In the Clutches of Chaos ---
    if "itcc_tablet_remove_breach" in pending:
        margin = _fail_margin(ctx)
        have = int(controller.s.vars.get("act_breaches", 0) or 0)
        removed = min(margin, have)
        if removed:
            controller.s.vars["act_breaches"] = have - removed
            log(f"💀 石板失败效果：从当前场景移除{removed}个破口")
        pending.discard("itcc_tablet_remove_breach")
    if "itcc_elder_random_breach" in pending:
        loc_ids = sorted(controller.game_state.locations.keys())
        if loc_ids:
            target = random.choice(loc_ids)
            breaches = _breaches(controller)
            breaches[target] = int(breaches.get(target, 0) or 0) + 1
            log(f"💀 旧神之物失败效果：随机地点【{target}】+1破口")
        pending.discard("itcc_elder_random_breach")

    # --- Before the Black Throne ---
    if "btbt_cultist_pull" in pending:
        pulled = _pull_enemy_matching(controller, _CULTIST)
        if pulled:
            cd = controller.game_state.get_card_data(pulled)
            log(f"💀 异教徒失败效果：抽到異教徒敌人《{cd.name_cn if cd else pulled}》"
                "（简化：不重洗遭遇牌堆）")
            controller._spawn_enemy_from_encounter(pulled, ctx.investigator_id)
        pending.discard("btbt_cultist_pull")
    if "btbt_tablet_azathoth_attack" in pending:
        aza = _azathoth_iid(controller)
        if aza is not None:
            _enemy_attacks(controller, ctx, inv, aza, "石板失败效果：阿撒托斯")
        pending.discard("btbt_tablet_azathoth_attack")


def on_success(controller, ctx, pending) -> None:
    """检定成功后的条件效果。

    TCU 8 个剧本的符号标记均无“若成功”分支（两面文本核对），
    本函数为接口对齐的空实现。
    """
    return None
