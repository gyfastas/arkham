"""Self-Sacrifice (Level 0) — Guardian Skill. (06157)
只能投入到你所在地点的另一位调查员执行的(任何类型的)技能检定中。
如果这次检定失败，检定失败的所有效果不由执行检定的调查员结算，改为必须由
你结算。然后，你或执行检定的调查员抽取2张卡牌。

简化说明：
- "只能投入另一位调查员的检定"由会话层校验（引擎提交通道不验证卡牌归属）。
- 失败效果改由你结算：引擎的失败回调（on_failure）以执行者身份直接结算，
  卡牌代码无法重定向；实现为写入 scenario.vars["self_sacrifice_redirect"]
  与 ctx.extra 标记供会话层/引擎消费（列为引擎缺口）。
- 抽牌选择自动为投入者（你）抽2张（官方"你或执行者"二选一的简化）。
"""

from backend.cards._shared import find_holder
from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class SelfSacrifice(CardImplementation):
    card_id = "self_sacrifice_lv0"

    @on_event(GameEvent.SKILL_TEST_FAILED, priority=TimingPriority.AFTER)
    def take_the_hit(self, ctx):
        """检定失败：失败效果改由投入者结算（标记），投入者抽2张牌。"""
        if self.card_id not in (ctx.committed_cards or []):
            return
        performer = ctx.game_state.get_investigator(ctx.investigator_id)
        owner = find_holder(ctx.game_state, self.card_id)
        if performer is None or owner is None:
            return
        if owner.investigator_id == performer.investigator_id:
            return  # 只能投入另一位调查员的检定
        if owner.location_id != performer.location_id:
            return

        # 失败效果重定向标记（会话层/引擎消费，见 docstring）
        ctx.game_state.scenario.vars["self_sacrifice_redirect"] = {
            "from": performer.investigator_id,
            "to": owner.investigator_id,
        }
        ctx.extra["self_sacrifice_redirect"] = owner.investigator_id

        # 然后抽2张牌（简化为投入者抽取）
        drawn = []
        for _ in range(2):
            if owner.deck:
                card_id = owner.deck.pop(0)
                owner.hand.append(card_id)
                drawn.append(card_id)
        ctx.extra["self_sacrifice_drew"] = drawn
        ctx.game_state.log_effect(
            f"💔 自我牺牲：{owner.investigator_id} 代为结算失败效果并抽{len(drawn)}张牌")
