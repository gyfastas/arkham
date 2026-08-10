"""Strength in Numbers (Level 1) — Survivor Skill. (08077)
你控制的卡牌之中每有一个不同的职阶，人多力量大获得一个 [wild] 图标。

简化说明：
- 按规则参考（控制与归属），"你控制的卡牌"包含你的调查员卡、你场上的卡
  以及你投入本次检定的卡；本实现按此三类统计不同职阶数 N，在投入时
  +N 个万能图标（卡面印刷的 1 个万能图标由引擎自动计入）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class StrengthInNumbers(CardImplementation):
    card_id = "strength_in_numbers_lv1"

    @on_event(GameEvent.SKILL_TEST_COMMIT, priority=TimingPriority.WHEN)
    def bonus_wild_icons(self, ctx):
        """投入时：每有一个不同职阶（你控制的卡）+1 万能图标。"""
        if self.card_id not in (ctx.committed_cards or []):
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return

        classes: set[str] = set()
        # 调查员卡
        inv_class = getattr(inv.card_data, "card_class", None)
        if inv_class is not None:
            classes.add(getattr(inv_class, "value", str(inv_class)))
        # 场上控制的卡
        for iid in inv.play_area:
            inst = ctx.game_state.get_card_instance(iid)
            if inst is None:
                continue
            cd = ctx.game_state.get_card_data(inst.card_id)
            if cd is not None and cd.card_class is not None:
                classes.add(getattr(cd.card_class, "value", str(cd.card_class)))
        # 投入本次检定的卡
        for card_id in (ctx.committed_cards or []):
            cd = ctx.game_state.get_card_data(card_id)
            if cd is not None and cd.card_class is not None:
                classes.add(getattr(cd.card_class, "value", str(cd.card_class)))

        if classes:
            ctx.modify_amount(len(classes), "strength_in_numbers_icons")
            ctx.extra["strength_in_numbers_classes"] = len(classes)
