"""Rex's Curse — Neutral Treachery, Signature Weakness (Rex Murphy).
显现：放置入你的威胁区域。
强制 - 在你将要技能检定成功时：将抽出的混乱标记放回袋中，再抽取1个新标记。
如果这个效果导致你检定失败，将雷克斯的诅咒与你的牌堆混洗。(每次检定限制1次。)

简化说明：
- 混沌袋通过 bind_chaos_bag() 注入（卡牌实现无法直接访问 Game.chaos_bag，
  会话层/测试在抽到后绑定）。未绑定时强制效果不触发。
- 标记修正值使用标准数值表，非数值特殊标记视为0，[auto_fail]视为失败。
- 成功翻失败依赖 skill_test 引擎对 ctx.success 的回读（已实现）。
"""

import random

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import (
    CHAOS_TOKEN_VALUES,
    ChaosTokenType,
    GameEvent,
    TimingPriority,
)


class RexsCurse(CardImplementation):
    card_id = "rexs_curse_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._used_this_test = False
        self._chaos_bag = None
        self._rng = random.Random()

    def bind_chaos_bag(self, chaos_bag) -> None:
        """注入混沌袋（Session/测试在抽到后调用）。"""
        self._chaos_bag = chaos_bag

    @on_event(GameEvent.CARD_DRAWN, priority=TimingPriority.WHEN)
    def revelation(self, ctx):
        if ctx.extra.get("card_id") != "rexs_curse_lv0":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if "rexs_curse_lv0" in inv.hand:
            inv.hand.remove("rexs_curse_lv0")

        from backend.models.state import CardInstance
        inst_id = ctx.game_state.next_instance_id()
        ci = CardInstance(
            instance_id=inst_id,
            card_id="rexs_curse_lv0",
            owner_id=ctx.investigator_id,
            controller_id=ctx.investigator_id,
        )
        ctx.game_state.cards_in_play[inst_id] = ci
        inv.threat_area.append(inst_id)

    @on_event(GameEvent.SKILL_TEST_BEGINS, priority=TimingPriority.WHEN)
    def reset_test_limit(self, ctx):
        self._used_this_test = False

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.WHEN)
    def forced_redraw(self, ctx):
        """将要成功时：重抽一个标记；若导致失败则把诅咒洗回牌堆。"""
        if self._used_this_test:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if self._find_curse(ctx.game_state, inv) is None:
            return
        if self._chaos_bag is None:
            return

        self._used_this_test = True

        # 再抽取1个新标记（简化：原标记不回袋，直接重抽）
        token = self._chaos_bag.draw()
        ctx.extra["rexs_curse_redrawn_token"] = token

        # 用新标记重新计算检定结果
        if token == ChaosTokenType.AUTO_FAIL:
            value = 0
            new_total = -999
        else:
            value = CHAOS_TOKEN_VALUES.get(token) or 0  # 特殊标记视为0
            old_value = ctx.extra.get("token_modifier", ctx.amount or 0)
            new_total = (ctx.modified_skill or 0) - old_value + value

        # The first successful event is still being processed, so update the
        # event context to the redrawn token's actual value before the engine
        # reads ctx.success back. This keeps the result and UI in sync.
        ctx.modified_skill = max(0, new_total)
        ctx.amount = value
        ctx.extra["rexs_curse_redrawn_token"] = token.value
        ctx.extra["rexs_curse_redrawn_modifier"] = value
        ctx.success = token != ChaosTokenType.AUTO_FAIL and new_total >= (ctx.difficulty or 0)

        if not ctx.success:
            ctx.extra["rexs_curse_caused_failure"] = True
            self._shuffle_back_into_deck(ctx.game_state, inv)

    def _shuffle_back_into_deck(self, game_state, inv) -> None:
        curse = self._find_curse(game_state, inv)
        if curse is None:
            return
        if curse.instance_id in inv.threat_area:
            inv.threat_area.remove(curse.instance_id)
        game_state.cards_in_play.pop(curse.instance_id, None)
        inv.deck.append("rexs_curse_lv0")
        self._rng.shuffle(inv.deck)

    @staticmethod
    def _find_curse(game_state, inv):
        for inst_id in inv.threat_area:
            inst = game_state.get_card_instance(inst_id)
            if inst is not None and inst.card_id == "rexs_curse_lv0":
                return inst
        return None
