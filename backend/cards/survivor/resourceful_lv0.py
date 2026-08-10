"""Resourceful (Level 0) — Survivor Skill.
如果本次技能检定成功，选择你弃牌堆中一张标题不是急中生智的[survivor]
卡牌。将选中的卡牌加入你的手牌。

简化说明：
- 目标选择简化：自动取弃牌堆中第一张符合条件的生存者卡
  （官方为玩家选择）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, PlayerClass, TimingPriority


class Resourceful(CardImplementation):
    card_id = "resourceful_lv0"

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.AFTER)
    def recover_survivor_card(self, ctx):
        """检定成功：回收弃牌堆中一张非急中生智的生存者卡。"""
        if self.card_id not in ctx.committed_cards:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        for cid in list(inv.discard):
            cd = ctx.game_state.get_card_data(cid)
            if cd is None or cd.card_class != PlayerClass.SURVIVOR:
                continue
            if cd.name == "Resourceful":
                continue
            inv.discard.remove(cid)
            inv.hand.append(cid)
            ctx.extra["resourceful_recovered"] = cid
            ctx.game_state.log_effect(
                f"♻️ 急中生智：检定成功，从弃牌堆回收【{ctx.game_state.card_name(cid)}】")
            return
