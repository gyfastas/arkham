"""Unsolved Case (Level 0) — Neutral Event, Signature Weakness (Joe Diamond).
费用4。
将你的1个线索放在隐藏值最高的地点。将悬案移出游戏。
强制 - 如果悬案将要混洗入你的直觉牌组：改为将其加入到你的威胁区域。
直到本场游戏结束，其获得："强制 - 当游戏结束时：乔·戴蒙德本场冒险
少获得2点经验值。"

简化说明：
- 打出效果（CARD_PLAYED）：持有者线索>0 时转移1个线索到隐藏值最高的
  地点（并列时取地点表序第一个），并记入 removed_from_game。引擎在
  CARD_PLAYED 结算后无条件将事件置入弃牌堆（actions._play_event），
  "移出游戏"以 vars 记录为准、弃牌堆中的残留由会话层过滤（引擎缺口）。
- 直觉牌组（hunch deck）是乔·戴蒙德的专属机制，引擎无对应区域；
  "将要洗入直觉牌组时改为加入威胁区域"由 on_shuffle_into_hunch_deck()
  表达，供会话层在洗入直觉牌组前调用。
- 游戏结束的经验惩罚由 game_end_penalty() 提供给会话/战役层结算。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority
from backend.models.state import CardInstance


class UnsolvedCase(CardImplementation):
    card_id = "unsolved_case_lv0"

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def play_effect(self, ctx):
        if ctx.extra.get("card_id") != "unsolved_case_lv0":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return

        # 将1个线索放在隐藏值最高的地点
        if inv.clues > 0 and ctx.game_state.locations:
            target = max(
                ctx.game_state.locations.values(),
                key=lambda loc: loc.shroud,
            )
            inv.clues -= 1
            target.clues += 1
            ctx.game_state.log_effect(
                f"🕵️ 悬案：1个线索放回【{target.location_id}】")
            ctx.extra["unsolved_case_location"] = target.location_id

        # 移出游戏（引擎随后仍会将事件置入弃牌堆，见 docstring）
        ctx.game_state.scenario.vars.setdefault(
            "removed_from_game", []).append("unsolved_case_lv0")

    def on_shuffle_into_hunch_deck(self, game_state, investigator_id) -> bool:
        """强制 - 将要洗入直觉牌组时：改为加入威胁区域。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return False
        ci = CardInstance(
            instance_id=game_state.next_instance_id(),
            card_id="unsolved_case_lv0",
            owner_id=investigator_id,
            controller_id=investigator_id,
        )
        game_state.cards_in_play[ci.instance_id] = ci
        inv.threat_area.append(ci.instance_id)
        game_state.log_effect("🕵️ 悬案：加入威胁区域（代替洗入直觉牌组）")
        return True

    def game_end_penalty(self, game_state, investigator_id) -> str | None:
        """游戏结束时悬案在威胁区域：本场冒险少获得2点经验值。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return None
        for inst_id in inv.threat_area:
            inst = game_state.get_card_instance(inst_id)
            if inst is not None and inst.card_id == "unsolved_case_lv0":
                xp = game_state.scenario.vars.setdefault("xp_modifiers", {})
                xp[investigator_id] = xp.get(investigator_id, 0) - 2
                return "悬案仍在威胁区域：本场冒险少获得2点经验值"
        return None
