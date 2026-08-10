"""Siren Call (Level 0) — Neutral Treachery, Weakness. (07016)
显现 - 将塞壬的召唤放置入你的威胁区域。
作为向技能检定投入1张或以上卡牌的额外费用，你必须为这些卡牌上每个
相匹配的技能图标支付1个资源。
[action][action]：丢弃塞壬的召唤。

简化说明：
- 投入附加费用在引擎投入通道（SKILL_TEST_COMMIT 仅统计图标、无费用
  校验）中无法拦截，由 commit_surcharge() 表达：会话层在玩家投入卡牌时
  调用，按匹配图标数扣资源；资源不足时返回 False（会话层应阻止该次投入）。
  另提供自动扣费兜底：SKILL_TEST_COMMIT 时若尚未收取则自动扣除，资源
  不足时在 ctx.extra 标记欠费（供会话层处理）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class SirenCall(CardImplementation):
    card_id = "siren_call_lv0"
    activations = [{"id": "discard", "label": "[行动×2] 丢弃塞壬的召唤", "method": "activate_discard", "actions": 2}]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._paid_this_test = False

    @on_event(GameEvent.CARD_DRAWN, priority=TimingPriority.WHEN)
    def revelation(self, ctx):
        if ctx.extra.get("card_id") != "siren_call_lv0":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if "siren_call_lv0" in inv.hand:
            inv.hand.remove("siren_call_lv0")

        from backend.models.state import CardInstance
        inst_id = ctx.game_state.next_instance_id()
        ci = CardInstance(
            instance_id=inst_id,
            card_id="siren_call_lv0",
            owner_id=ctx.investigator_id,
            controller_id=ctx.investigator_id,
        )
        ctx.game_state.cards_in_play[inst_id] = ci
        inv.threat_area.append(inst_id)

    def surcharge(self, game_state, investigator_id, committed_card_ids, skill_type) -> int:
        """计算投入的附加费用：投入卡牌上与检定技能相匹配的图标总数。"""
        total = 0
        key = getattr(skill_type, "value", skill_type)
        for cid in committed_card_ids or []:
            cd = game_state.get_card_data(cid)
            if cd is None or not cd.skill_icons:
                continue
            total += cd.skill_icons.get(key, 0)
            total += cd.skill_icons.get("wild", 0)
        return total

    def commit_surcharge(self, game_state, investigator_id, committed_card_ids, skill_type) -> bool:
        """会话层在投入时调用：收取附加费用，资源不足返回 False。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return True
        cost = self.surcharge(game_state, investigator_id, committed_card_ids, skill_type)
        if cost <= 0:
            return True
        if inv.resources < cost:
            return False
        inv.resources -= cost
        self._paid_this_test = True
        return True

    @on_event(GameEvent.SKILL_TEST_COMMIT, priority=TimingPriority.WHEN)
    def auto_surcharge(self, ctx):
        """兜底：会话层未预扣时自动收取附加费用（资源不足则标记欠费）。"""
        if self._paid_this_test:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self._find(ctx.game_state, inv) is None:
            return
        if not (ctx.committed_cards or []):
            return
        cost = self.surcharge(ctx.game_state, ctx.investigator_id,
                              ctx.committed_cards, ctx.skill_type)
        if cost <= 0:
            return
        if inv.resources >= cost:
            inv.resources -= cost
            ctx.extra["siren_call_surcharge"] = cost
        else:
            ctx.extra["siren_call_unpaid"] = cost

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._paid_this_test = False

    def activate_discard(self, game_state, investigator_id) -> bool:
        """[action][action]：丢弃塞壬的召唤。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return False
        inst = self._find(game_state, inv)
        if inst is None:
            return False
        inv.threat_area.remove(inst.instance_id)
        game_state.cards_in_play.pop(inst.instance_id, None)
        inv.discard.append("siren_call_lv0")
        return True

    @staticmethod
    def _find(game_state, inv):
        for inst_id in inv.threat_area:
            inst = game_state.get_card_instance(inst_id)
            if inst is not None and inst.card_id == "siren_call_lv0":
                return inst
        return None
