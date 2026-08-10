"""Daring (Level 0) — Guardian Skill. (06111)
仅可投入到对敌人的攻击或躲避中的技能检定。该敌人在本次技能检定期间
获得反击和警戒。本次检定结束后，抽1张牌。

简化说明：
- 3个任意图标由 skill_icons 数据经提交流程自动结算。
- "该敌人获得反击/警戒"：⚠️ 引擎缺口——SKILL_TEST_COMMIT 上下文不含检定
  目标敌人（FIGHT/EVADE 的目标不传入检定 ctx），无法定位授予对象，未实现
  （见报告）。
- "检定结束后抽1张牌"：SKILL_TEST_ENDS 触发（本实现实例仅在作为投入卡被
  激活时挂在总线上，即天然限定"投入本卡的检定"）。抽牌者为检定者
  （投入他人检定的归属差異从简）。
- "仅可投入攻击/躲避"为投入限制：引擎无投入校验钩子，无法阻止其他检定
  投入（同 not_without_a_fight 注明）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class Daring(CardImplementation):
    card_id = "daring_lv0"

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def draw_after_test(self, ctx):
        """本次检定结束后：抽1张牌。"""
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or not inv.deck:
            return
        card_id = inv.deck.pop(0)
        inv.hand.append(card_id)
        ctx.extra["daring_drew"] = card_id
        ctx.game_state.log_effect(
            f"🃏 浑身是胆：检定结束，抽到【{ctx.game_state.card_name(card_id)}】")
