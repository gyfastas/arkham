"""The King in Yellow (Level 0) — Neutral Asset, Signature Weakness (Minh Thi Phan).
显现：放置入你的威胁区域。除非通过下述[reaction]能力，否则不能离场。
你不能在技能检定中投入正好1或2张卡牌。
[reaction]技能检定成功且潘明投入至少6个与该检定对应的技能图标后：丢弃黄衣之王。

简化说明：
- "不能投入正好1或2张卡"是投入窗口限制，由 can_commit() 表达；引擎提交通道
  不做投入数量校验——需要引擎/会话侧接线（与 inquiring_mind_lv0 同一缺口）。
- "对应的技能图标"计入与检定技能相同的图标及狂野图标（官方 FAQ 狂野计入）。
- "不能离场"没有通用离场拦截钩子，需要引擎支持。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority
from backend.models.state import CardInstance


class TheKingInYellow(CardImplementation):
    card_id = "the_king_in_yellow_lv0"

    @on_event(GameEvent.CARD_DRAWN, priority=TimingPriority.WHEN)
    def revelation(self, ctx):
        if ctx.extra.get("card_id") != "the_king_in_yellow_lv0":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if "the_king_in_yellow_lv0" in inv.hand:
            inv.hand.remove("the_king_in_yellow_lv0")

        inst_id = ctx.game_state.next_instance_id()
        ci = CardInstance(
            instance_id=inst_id,
            card_id="the_king_in_yellow_lv0",
            owner_id=ctx.investigator_id,
            controller_id=ctx.investigator_id,
        )
        ctx.game_state.cards_in_play[inst_id] = ci
        inv.threat_area.append(inst_id)

    def can_commit(self, game_state, investigator_id, num_cards: int) -> bool:
        """官方投入限制：黄衣之王在威胁区时，不能投入正好1或2张卡。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return True
        if self._find_in_threat(game_state, inv) is None:
            return True
        return num_cards not in (1, 2)

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.REACTION)
    def discard_on_six_icons(self, ctx):
        """检定成功且投入≥6个对应技能图标后：丢弃黄衣之王。"""
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        inst = self._find_in_threat(ctx.game_state, inv)
        if inst is None:
            return
        skill_key = ctx.skill_type.value if ctx.skill_type else ""
        icons = 0
        for cid in ctx.committed_cards or []:
            cd = ctx.game_state.get_card_data(cid)
            if cd is None or not cd.skill_icons:
                continue
            icons += cd.skill_icons.get(skill_key, 0)
            icons += cd.skill_icons.get("wild", 0)
        if icons < 6:
            return
        inv.threat_area.remove(inst.instance_id)
        ctx.game_state.cards_in_play.pop(inst.instance_id, None)
        inv.discard.append("the_king_in_yellow_lv0")
        ctx.game_state.log_effect("👑 黄衣之王：投入6个对应图标且检定成功，丢弃黄衣之王")

    @staticmethod
    def _find_in_threat(game_state, inv):
        for inst_id in inv.threat_area:
            inst = game_state.get_card_instance(inst_id)
            if inst is not None and inst.card_id == "the_king_in_yellow_lv0":
                return inst
        return None
