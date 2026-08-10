"""Daring Maneuver (Level 0) — Rogue Event.
快速。在你技能检定将要成功时打出。这次技能检定你+2技能值。

简化说明：
- 从手牌中自动触发：检定成功（SKILL_TEST_SUCCESSFUL）时若手牌中有本卡，
  自动打出（费用0）并将本次检定的修正后技能值+2（lucky 同模式；
  官方为玩家自行选择打出时机，仅在"超出难度"类效果有意义时使用）。
- +2 通过改写 ctx.modified_skill 生效：同事件内后续优先级（AFTER）的
  超出难度判定（如折刀、.41大口径短口手枪）会看到提高后的数值；
  引擎不回读 modified_skill，成败结果本身不受影响（本就已成功）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class DaringManeuver(CardImplementation):
    card_id = "daring_maneuver_lv0"
    persistent_in_hand = True  # 在手牌中持续监听"将要成功"窗口

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.WHEN)
    def boost_on_success(self, ctx):
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.card_id not in inv.hand:
            return

        # 自动打出（简化：官方为玩家选择时机；费用0）
        cd = ctx.game_state.get_card_data(self.card_id)
        cost = (getattr(cd, "cost", 0) or 0) if cd else 0
        if inv.resources < cost:
            return
        inv.resources -= cost
        inv.hand.remove(self.card_id)
        inv.discard.append(self.card_id)

        ctx.modified_skill = (ctx.modified_skill or 0) + 2
        ctx.extra["daring_maneuver_boost"] = True
        ctx.game_state.log_effect("🤸 大胆机动：+2技能值（将要成功时打出）")
