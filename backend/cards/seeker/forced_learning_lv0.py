"""Forced Learning (Level 0) — Seeker Asset, Permanent. (08031)
永久。每副牌组限制1张。当牌组构建时购买。你的牌组卡牌张数加15。
补给阶段中，不抽取1张卡牌，改为抽取2张卡牌并丢弃其中1张。

简化说明：
- "牌组+15"与"永久（开局在场）"属组牌/开局流程，由会话层负责，本卡
  仅实现在场时的补给阶段修正；
- 引擎的 upkeep 抽牌（phase_upkeep._draw_and_resource）无拦截钩子
  （引擎缺口），故实现为：补给阶段内侦测到本卡持有者的 upkeep 抽牌
  （CARD_DRAWN）后，立即补抽1张并从这两张中弃1张——净效果与官方
  "抽2弃1代替抽1"一致，且发生在手牌上限检查之前；
- "弃其中1张"自动选择费用较低者（平费时弃补抽的那张；官方为玩家自选）；
- 补抽不发 CARD_DRAWN（避免递归；抽到弱点不触发揭示，已知简化）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Phase, TimingPriority


class ForcedLearning(CardImplementation):
    card_id = "forced_learning_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._pending: str | None = None  # 本 upkeep 已抽第1张、待补抽弃1的调查员

    @on_event(GameEvent.UPKEEP_PHASE_BEGINS, priority=TimingPriority.AFTER)
    def reset_for_upkeep(self, ctx):
        self._pending = None

    @on_event(GameEvent.CARD_DRAWN, priority=TimingPriority.AFTER)
    def draw_extra_and_discard(self, ctx):
        """补给阶段的抽牌改为抽2弃1（补抽第2张后从两张中弃1张）。"""
        if ctx.game_state.scenario.current_phase != Phase.UPKEEP:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        if self._pending is not None:
            return  # 本阶段已处理
        first_drawn = ctx.extra.get("card_id")
        if first_drawn is None or first_drawn not in inv.hand:
            return
        self._pending = inv.investigator_id

        # 补抽第2张
        second_drawn = None
        if inv.deck:
            second_drawn = inv.deck.pop(0)
            inv.hand.append(second_drawn)

        if second_drawn is None:
            return  # 牌堆空：无法补抽，等效官方"改为抽2"只抽到1张，不弃
        # 从两张中弃1张：自动弃费用较低者（平费弃补抽的）
        cost_first = self._cost(ctx, first_drawn)
        cost_second = self._cost(ctx, second_drawn)
        discard = first_drawn if cost_first < cost_second else second_drawn
        inv.hand.remove(discard)
        inv.discard.append(discard)
        ctx.extra["forced_learning_kept"] = (
            second_drawn if discard == first_drawn else first_drawn
        )
        ctx.extra["forced_learning_discarded"] = discard
        ctx.game_state.log_effect(
            f"📖 强行学习：补给抽2弃1，弃掉【{ctx.game_state.card_name(discard)}】"
        )

    @staticmethod
    def _cost(ctx, card_id: str) -> int:
        cd = ctx.game_state.get_card_data(card_id)
        return cd.cost if (cd is not None and cd.cost is not None) else 99
