"""Deny Existence (Level 0) — Mystic Event. (05032)
快速。在一张遭遇卡或一次敌人攻击将会导致你执行以下一项（选择一项）时打出：
丢弃手牌、失去资源、失去行动、受到伤害或受到恐惧。你忽略该效果的那个方面。
（其它方面正常结算。）

简化说明：
- 从手牌中自动触发（同 a_test_of_will 惯例）：你被分配伤害或恐惧时，
  若手牌中有否决存在（0费），自动打出并取消该次分配（lv0 仅取消，
  lv5 追加反向效果）。
- 官方"遭遇卡/敌人攻击"来源限定无法精确识别（DAMAGE_ASSIGNED 仅有
  source 实例id，遭遇卡直接伤害常无来源）；简化为任何来源均可触发。
- "丢弃手牌/失去资源/失去行动"三个方面无引擎事件通道（引擎缺口）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class DenyExistence(CardImplementation):
    card_id = "deny_existence_lv0"
    reverse_effect = False  # lv5 覆盖：忽略后执行相反效果

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._spent = False

    def _try_deny(self, ctx, aspect: str) -> None:
        """持有者被分配伤害/恐惧时：自动打出并取消该方面。"""
        if self._spent:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.card_id not in inv.hand:
            return

        # 0费：直接打出
        inv.hand.remove(self.card_id)
        inv.discard.append(self.card_id)
        self._spent = True

        amount = ctx.amount or 0
        ctx.cancel()  # 忽略该方面
        ctx.extra[f"{self.card_id}_ignored_{aspect}"] = amount

        if self.reverse_effect and amount > 0:
            # lv5：执行相反效果（治愈等量伤害/恐惧）
            if aspect == "damage":
                inv.damage = max(0, inv.damage - amount)
            else:
                inv.horror = max(0, inv.horror - amount)
            ctx.extra[f"{self.card_id}_reversed_{aspect}"] = amount
            ctx.game_state.log_effect(
                f"✨ 否决存在：忽略{amount}点{aspect}并治愈等量")
        else:
            ctx.game_state.log_effect(f"✨ 否决存在：忽略{amount}点{aspect}")

    @on_event(GameEvent.DAMAGE_ASSIGNED, priority=TimingPriority.WHEN)
    def deny_damage(self, ctx):
        self._try_deny(ctx, "damage")

    @on_event(GameEvent.HORROR_ASSIGNED, priority=TimingPriority.WHEN)
    def deny_horror(self, ctx):
        self._try_deny(ctx, "horror")
