"""Cheat the System (Level 1) — Rogue Event. (08050)
快速。在任何[快速]时间段中打出。
你控制的卡牌之中每有一个不同的职阶，获得1资源。

实现说明：
- 打出时机由会话层快速窗口校验。
- 统计你场上（play_area）卡牌数据 card_class 的去重数量；调查员卡本身
  不计（官方"你控制的卡牌"指你控制的场上卡牌，含盟友/支援等）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class CheatTheSystem(CardImplementation):
    card_id = "cheat_the_system_lv1"

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.AFTER)
    def gain_per_class(self, ctx):
        """你控制的卡牌每有一个不同职阶：获得1资源。"""
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        classes = set()
        for iid in inv.play_area:
            inst = ctx.game_state.get_card_instance(iid)
            if inst is None:
                continue
            cd = ctx.game_state.get_card_data(inst.card_id)
            if cd is not None and cd.card_class is not None:
                classes.add(cd.card_class)
        if not classes:
            return
        inv.resources += len(classes)
        ctx.extra["cheat_the_system_classes"] = len(classes)
        ctx.game_state.log_effect(
            f"🎭 欺骗制度：控制{len(classes)}个不同职阶，获得{len(classes)}资源")
