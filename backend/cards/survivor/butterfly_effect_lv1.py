"""Butterfly Effect (Level 1) — Survivor Event.
快速。在你所在地点的技能检定中揭示带符号的混乱标记时打出（在结算其效果前）。
你或执行检定的调查员可以投入一张卡牌到本次检定，或将一张已投入的卡牌
返回其手牌。

简化说明：
- 从手牌自动打出（persistent_in_hand，费用0）：同地点检定揭示符号标记
  （骷髅/异教徒/石板/古神/远古印记/自动失败/祝福/诅咒/寒霜，即非数字标记）
  且执行者有已投入卡牌时自动打出。
- 两种模式自动选择"返回已投入卡牌"（官方为玩家选择投入或返回；投入模式
  涉及检定中途补投，引擎无投入通道，未实现——引擎缺口）：
  自动返回最后一张投入的卡牌，经 SKILL_VALUE_DETERMINED 扣回其图标，
  并在 SKILL_TEST_ENDS 将其从弃牌堆救回手牌（ST.8 会先将其弃置）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import ChaosTokenType, GameEvent, TimingPriority

# 符号标记（卡面"chaos token with a symbol"）：非数字修正的所有标记。
_SYMBOL_TOKENS = {
    ChaosTokenType.SKULL, ChaosTokenType.CULTIST, ChaosTokenType.TABLET,
    ChaosTokenType.ELDER_THING, ChaosTokenType.AUTO_FAIL,
    ChaosTokenType.ELDER_SIGN, ChaosTokenType.BLESS, ChaosTokenType.CURSE,
    ChaosTokenType.FROST,
}


class ButterflyEffect(CardImplementation):
    card_id = "butterfly_effect_lv1"
    persistent_in_hand = True  # 在手牌中持续监听符号标记揭示窗口

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        # {investigator_id: [committed_card_ids]} 本次检定的投入快照
        self._committed: dict[str, list[str]] = {}
        # {investigator_id: card_id} 待返回手牌的卡牌
        self._returning: dict[str, str] = {}

    @on_event(GameEvent.SKILL_TEST_COMMIT, priority=TimingPriority.WHEN)
    def snapshot_committed(self, ctx):
        self._committed[ctx.investigator_id] = list(ctx.committed_cards or [])

    @on_event(GameEvent.CHAOS_TOKEN_REVEALED, priority=TimingPriority.WHEN)
    def play_on_symbol_token(self, ctx):
        if ctx.chaos_token not in _SYMBOL_TOKENS:
            return
        performer = ctx.game_state.get_investigator(ctx.investigator_id)
        if performer is None:
            return
        committed = self._committed.get(ctx.investigator_id) or []
        if not committed:
            return
        # 持有者须与执行者同地点
        holder = None
        for cand in ctx.game_state.investigators.values():
            if cand.location_id == performer.location_id and self.card_id in cand.hand:
                holder = cand
                break
        if holder is None:
            return

        # 自动打出（费用0）
        holder.hand.remove(self.card_id)
        holder.discard.append(self.card_id)

        # 自动选择：返回执行者最后一张投入的卡牌
        returned = committed[-1]
        self._returning[ctx.investigator_id] = returned
        ctx.extra["butterfly_effect_returned"] = returned
        ctx.game_state.log_effect(
            f"🦋 蝴蝶效应：将已投入的【{ctx.game_state.card_name(returned)}】返回手牌")

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def remove_returned_icons(self, ctx):
        """扣回被返回卡牌提供的图标（投入已在ST.2计入）。"""
        returned = self._returning.get(ctx.investigator_id)
        if returned is None:
            return
        cd = ctx.game_state.get_card_data(returned)
        if cd is None or not cd.skill_icons:
            return
        icons = cd.skill_icons.get(ctx.skill_type.value, 0) \
            + cd.skill_icons.get("wild", 0)
        if icons:
            ctx.modify_amount(-icons, "butterfly_effect_return")

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def rescue_and_clear(self, ctx):
        """ST.8 已把投入卡弃置：将被返回的卡牌从弃牌堆救回手牌。"""
        try:
            returned = self._returning.get(ctx.investigator_id)
            if returned is None:
                return
            inv = ctx.game_state.get_investigator(ctx.investigator_id)
            if inv is not None and returned in inv.discard:
                inv.discard.remove(returned)
                inv.hand.append(returned)
        finally:
            self._committed.pop(ctx.investigator_id, None)
            self._returning.pop(ctx.investigator_id, None)
