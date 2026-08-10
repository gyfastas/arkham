"""Grisly Totem (Level 3) — Survivor Asset, Accessory slot. (05195)
[reaction] After you commit a card to a skill test, exhaust Grisly Totem:
That card gains another instance of one of its skill icons of your choice.
If that skill test fails, return that card to your hand.

简化说明：
- 图标选择自动化（同 lv0）：净效果为本次检定 +1 图标。
- "返回手牌"在 SKILL_TEST_ENDS 结算：引擎在 ST.8 已将投入卡从手牌弃置，
  此处从弃牌堆取回（净效果与官方一致）。覆盖父类 clear 以保证
  先取回再清状态（同名事件的多个处理按方法名字典序注册）。
"""

from backend.cards.survivor.grisly_totem_lv0 import GrislyTotem
from backend.cards.base import on_event
from backend.models.enums import GameEvent, TimingPriority


class GrislyTotemLv3(GrislyTotem):
    card_id = "grisly_totem_lv3"

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        """检定失败：被加成的投入卡从弃牌堆返回手牌，然后清理状态。"""
        card_id = self._boosted_card
        if card_id is not None and ctx.success is False:
            inv = ctx.game_state.get_investigator(ctx.investigator_id)
            if inv is not None and card_id in inv.discard:
                inv.discard.remove(card_id)
                inv.hand.append(card_id)
                ctx.game_state.log_effect(
                    f"🗿 阴森图腾：检定失败，【{ctx.game_state.card_name(card_id)}】"
                    "返回手牌")
        self._boosted_card = None
