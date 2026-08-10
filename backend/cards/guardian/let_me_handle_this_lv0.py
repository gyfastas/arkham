""""Let me handle this!" (Level 0) — Guardian Event. (03022)
快速。另一位调查员抽取了1张非祸害遭遇卡后、结算该卡牌效果前打出。
改为你被视为抽取了该遭遇卡。结算该卡牌的显现效果时，你每项技能+2。

简化说明：
- 从手牌中自动触发（官方为玩家选择时机）：另一位调查员抽到非祸害
  （peril）遭遇卡时，若手牌中有本卡则自动打出（0费），同 ward_of_protection
  的自动打出约定。
- 重定向经 ctx.extra["redirect_to"] 与 scenario.vars["encounter_redirect"]
  标记提供给会话层（you_handle_this_one 同款约定的反向；会话层目前仅消费
  cancelled_encounter，重定向消费为会话缺口，见报告）。
- "+2每项技能"在事件发射链内同步生效：引擎在结算遭遇显现时启动的技能检定
  会获得+2；无检定的显现效果不受影响。标记在下次检定结束或神话阶段结束时
  清除。
"""

from backend.cards._shared import find_holder
from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class LetMeHandleThis(CardImplementation):
    card_id = "let_me_handle_this_lv0"
    persistent_in_hand = True  # 手牌中持续监听遭遇抽取

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._armed_for = None  # 获得+2的调查员 id

    @on_event(GameEvent.ENCOUNTER_CARD_DRAWN, priority=TimingPriority.WHEN)
    def redirect_encounter(self, ctx):
        """另一位调查员抽到非祸害遭遇卡：改为持有者被视为抽取了它。"""
        drawer = ctx.game_state.get_investigator(ctx.investigator_id)
        if drawer is None:
            return
        holder = find_holder(ctx.game_state, self.card_id)
        if holder is None or holder.investigator_id == drawer.investigator_id:
            return
        card_id = ctx.extra.get("card_id")
        card_data = ctx.game_state.get_card_data(card_id) if card_id else None
        if card_data is not None and "peril" in (card_data.keywords or []):
            return
        data = ctx.game_state.get_card_data(self.card_id)
        cost = (getattr(data, "cost", 0) or 0) if data else 0
        if holder.resources < cost:
            return

        # 从手牌打出（支付费用）
        holder.resources -= cost
        holder.hand.remove(self.card_id)
        holder.discard.append(self.card_id)

        # 重定向标记（会话层消费）
        ctx.extra["redirect_to"] = holder.investigator_id
        ctx.game_state.scenario.vars["encounter_redirect"] = {
            "card_id": card_id,
            "from": drawer.investigator_id,
            "to": holder.investigator_id,
        }
        self._armed_for = holder.investigator_id
        ctx.game_state.log_effect(
            f"✋ 让我来！：【{ctx.game_state.card_name(card_id)}】改由你抽取，"
            "结算显现效果时全技能+2")

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def plus_two_all_skills(self, ctx):
        """结算该遭遇显现效果期间：持有者每项技能+2。"""
        if self._armed_for is None or ctx.investigator_id != self._armed_for:
            return
        ctx.modify_amount(2, "let_me_handle_this_bonus")

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    @on_event(GameEvent.MYTHOS_PHASE_ENDS, priority=TimingPriority.AFTER)
    def disarm(self, ctx):
        self._armed_for = None
