"""Patrice Hathaway — Survivor Investigator.
能力：你的手牌上限减少3张。
每个补给阶段中，不抽取1张卡牌，改为丢弃你手牌中的所有非弱点卡牌，并抽取卡牌
直到你有5张手牌。
远古印记：+1。在这次检定结束后，你可以留下弃牌堆中的1张卡牌并将其余卡牌混洗回
你的牌堆。

简化说明：
- 手牌上限-3：补给阶段的逐调查员 UPKEEP_PHASE_BEGINS 上下文带 amount=8
  （engine/phase_upkeep.py 的手牌上限检查通道），对其 modify_amount(-3)。
- 补给抽牌替换：引擎在 phase_upkeep._draw_and_resource 中直接抽1张再发
  CARD_DRAWN，无"将要抽牌"拦截钩子；实现为在每个补给阶段派翠斯的第一次
  CARD_DRAWN 时撤销该抽牌（放回牌库顶），再结算官方替换效果（弃全部非弱点
  手牌、抽至5张）。替换抽牌不发出 CARD_DRAWN（避免递归；与 sefina_rousseau
  补抽同一惯例），其中抽到弱点也不做搁置/显现处理——遗留简化。
  牌库抽空时停止抽牌（不触发"弃牌堆洗回+1恐惧"，引擎缺口）。
- 远古印记的"留下1张"为玩家选择：优先读取一次性预设
  scenario.vars["patrice_hathaway_keep"]（card_id，或 "decline" 放弃整个效果，
  结算后弹出）；无预设时默认留下弃牌堆顶的1张（最近弃置）。
"""

import random

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import ChaosTokenType, GameEvent, Phase, TimingPriority
from backend.models.state import is_weakness_card

TARGET_HAND_SIZE = 5
HAND_SIZE_PENALTY = 3


class PatriceHathaway(CardImplementation):
    card_id = "patrice_hathaway"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._upkeep_draw_replaced = False
        self._resolving_upkeep = False
        self._elder_sign_pending = False

    def _get_patrice(self, game_state, investigator_id):
        """Return the investigator state iff it is Patrice Hathaway."""
        if investigator_id is None:
            return None
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return None
        card_data = getattr(inv, "card_data", None)
        if card_data is None or card_data.id != "patrice_hathaway":
            return None
        return inv

    @on_event(GameEvent.UPKEEP_PHASE_BEGINS, priority=TimingPriority.WHEN)
    def reduce_hand_size(self, ctx):
        """手牌上限-3（仅逐调查员的手牌检查上下文带 amount）；并重置补给抽牌标记。"""
        if ctx.investigator_id is None:
            # 阶段级事件：重置本阶段的抽牌替换标记
            self._upkeep_draw_replaced = False
            return
        inv = self._get_patrice(ctx.game_state, ctx.investigator_id)
        if inv is None or not ctx.amount:
            return
        ctx.modify_amount(-HAND_SIZE_PENALTY, "patrice_hathaway_hand_size")

    @on_event(GameEvent.CARD_DRAWN, priority=TimingPriority.AFTER)
    def replace_upkeep_draw(self, ctx):
        """补给阶段的抽牌替换为：弃全部非弱点手牌，然后抽至5张。"""
        if self._resolving_upkeep or self._upkeep_draw_replaced:
            return
        scenario = getattr(ctx.game_state, "scenario", None)
        if scenario is None or scenario.current_phase != Phase.UPKEEP:
            return
        inv = self._get_patrice(ctx.game_state, ctx.investigator_id)
        if inv is None:
            return

        self._resolving_upkeep = True
        self._upkeep_draw_replaced = True
        try:
            # 撤销引擎的补给抽牌（该牌放回牌库顶），使"不抽取1张卡牌"成立
            drawn = ctx.extra.get("card_id")
            if drawn and drawn in inv.hand:
                inv.hand.remove(drawn)
                inv.deck.insert(0, drawn)

            # 丢弃所有非弱点手牌
            discarded = 0
            for card_id in list(inv.hand):
                if is_weakness_card(ctx.game_state.get_card_data(card_id)):
                    continue
                inv.hand.remove(card_id)
                inv.discard.append(card_id)
                discarded += 1

            # 抽取卡牌直到5张手牌
            while len(inv.hand) < TARGET_HAND_SIZE and inv.deck:
                inv.hand.append(inv.deck.pop(0))

            ctx.game_state.log_effect(
                f"🎻 派翠斯·海瑟薇：补给阶段弃{discarded}张非弱点手牌，"
                f"抽至{len(inv.hand)}张手牌"
            )
        finally:
            self._resolving_upkeep = False

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.WHEN)
    def elder_sign_effect(self, ctx):
        """远古印记：+1。检定结束后可将弃牌堆除1张外混洗回牌堆。"""
        if ctx.chaos_token != ChaosTokenType.ELDER_SIGN:
            return
        inv = self._get_patrice(ctx.game_state, ctx.investigator_id)
        if inv is None:
            return
        ctx.modify_amount(1, "patrice_hathaway_elder_sign")
        self._elder_sign_pending = True

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def elder_sign_shuffle_discard(self, ctx):
        """检定结束：留下弃牌堆中1张，其余混洗回牌堆。"""
        if not self._elder_sign_pending:
            return
        self._elder_sign_pending = False
        inv = self._get_patrice(ctx.game_state, ctx.investigator_id)
        if inv is None or not inv.discard:
            return

        scenario = getattr(ctx.game_state, "scenario", None)
        keep = scenario.vars.pop("patrice_hathaway_keep", None) if scenario else None
        if keep == "decline":
            return
        if keep not in inv.discard:
            keep = inv.discard[-1]  # 默认留下弃牌堆顶

        rest = list(inv.discard)
        rest.remove(keep)
        inv.discard[:] = [keep]
        inv.deck.extend(rest)
        random.shuffle(inv.deck)
        ctx.game_state.log_effect(
            f"🎻 派翠斯·海瑟薇：远古印记，留下【{ctx.game_state.card_name(keep)}】，"
            f"{len(rest)}张弃牌混洗回牌堆"
        )
