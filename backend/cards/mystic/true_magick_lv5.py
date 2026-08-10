"""True Magick (Level 5) — Mystic Asset, Hand/Arcane slot. (08070)
使用(1充能)。每轮开始时重新补满此充能。
你可以借由揭示你手牌中的[[法术]]支援卡来结算其能力。将本卡视为被揭示的
支援卡（支付其费用、花费其充能、执行其效果等）。

简化/缺口说明：
- 充能 replenishment 完整实现：每轮开始时补满1充能。
- "揭示手牌中的法术支援并结算其能力"需要会话层/UI 选择目标并把该法术的
  能力路由到本卡实例（卡实现拿不到其他卡的激活通道，且被揭示卡不在场上），
  为引擎/会话缺口，未实现。
"""

from backend.cards.base import CardImplementation, on_event
from backend.cards.seeker._uses import uses_count, uses_key
from backend.models.enums import GameEvent, TimingPriority


class TrueMagick(CardImplementation):
    card_id = "true_magick_lv5"

    @on_event(GameEvent.ROUND_BEGINS, priority=TimingPriority.AFTER)
    def replenish_charge(self, ctx):
        """每轮开始：补满1充能。"""
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None:
            return
        if uses_count(inst, "charges") < 1:
            inst.uses[uses_key(inst, "charges")] = 1
            ctx.game_state.log_effect("📖 真法魔典：轮次开始，补满充能")
