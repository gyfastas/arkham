"""Mandy Thompson — Seeker Investigator.
能力：[reaction]在一位调查员在你所在地点将要在其牌堆或遭遇牌堆中查找并结算
某一效果时：该调查员可以查找额外3张卡牌，或该次查找多结算1个目标。(每轮限制一次)
远古印记：+0。在你的牌堆顶部3张卡牌中查找一张卡牌，并将其抽取或投入这次检定
(如果可能)。混洗你的牌堆。

简化说明：
- [reaction]反应能力未实现——引擎缺口：查找（search）效果由各卡牌实现内部
  内联完成（如 arcane_initiate_lv0 直接读取 inv.deck[:3]），引擎无统一的
  "将要查找"事件/钩子，不修改引擎或其他卡文件的前提下无法拦截。
- 远古印记的查找+选择为玩家选择：优先读取一次性预设
  scenario.vars["mandy_thompson_elder_sign"]
  （{"card_id": ..., "mode": "draw"|"commit"}，结算后弹出）；无预设时默认抽取
  顶部3张中的第1张（官方为玩家任选一张）。查找后混洗牌堆。
- "投入这次检定(如果可能)"：远古印记在 ST.4 结算，晚于投入窗口（ST.2），
  无法进入正式投入通道；近似为将被投卡牌匹配当前检定的技能图标（含 wild）
  经 SKILL_VALUE_DETERMINED 加到检定值上，卡牌于 SKILL_TEST_ENDS 时入弃牌堆。
  被投卡牌自身的投入效果不触发——引擎缺口。
"""

import random

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import ChaosTokenType, GameEvent, TimingPriority

SEARCH_COUNT = 3


class MandyThompson(CardImplementation):
    card_id = "mandy_thompson"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._committed_card: str | None = None
        self._committed_icons = 0

    def _get_mandy(self, game_state, investigator_id):
        """Return the investigator state iff it is Mandy Thompson."""
        if investigator_id is None:
            return None
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return None
        card_data = getattr(inv, "card_data", None)
        if card_data is None or card_data.id != "mandy_thompson":
            return None
        return inv

    def _icons_for(self, game_state, card_id, skill_type) -> int:
        if skill_type is None:
            return 0
        card_data = game_state.get_card_data(card_id)
        if card_data is None or not card_data.skill_icons:
            return 0
        return (
            card_data.skill_icons.get(skill_type.value, 0)
            + card_data.skill_icons.get("wild", 0)
        )

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.WHEN)
    def elder_sign_effect(self, ctx):
        """远古印记：+0。查找牌堆顶3张，抽一张或投入本次检定，然后混洗牌堆。"""
        if ctx.chaos_token != ChaosTokenType.ELDER_SIGN:
            return
        inv = self._get_mandy(ctx.game_state, ctx.investigator_id)
        if inv is None:
            return

        top = inv.deck[:SEARCH_COUNT]
        if not top:
            return

        scenario = getattr(ctx.game_state, "scenario", None)
        preset = scenario.vars.pop("mandy_thompson_elder_sign", None) if scenario else None
        chosen = top[0]
        mode = "draw"
        if preset:
            if preset.get("card_id") in top:
                chosen = preset["card_id"]
            if preset.get("mode") in ("draw", "commit"):
                mode = preset["mode"]

        icons = self._icons_for(ctx.game_state, chosen, ctx.skill_type)
        if mode == "commit" and icons > 0:
            inv.deck.remove(chosen)
            self._committed_card = chosen
            self._committed_icons = icons
            ctx.game_state.log_effect(
                f"🔬 曼蒂·汤普森：远古印记，将【{ctx.game_state.card_name(chosen)}】"
                f"投入本次检定（+{icons}图标）"
            )
        else:
            inv.deck.remove(chosen)
            inv.hand.append(chosen)
            ctx.game_state.log_effect(
                f"🔬 曼蒂·汤普森：远古印记，抽取牌堆顶3张中的"
                f"【{ctx.game_state.card_name(chosen)}】"
            )
        random.shuffle(inv.deck)

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def apply_committed_icons(self, ctx):
        """远古印记投入的卡牌图标加到检定值上（ST.4 后的近似通道）。"""
        if self._committed_card is None:
            return
        inv = self._get_mandy(ctx.game_state, ctx.investigator_id)
        if inv is None:
            return
        ctx.modify_amount(self._committed_icons, "mandy_thompson_elder_sign_commit")

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def discard_committed_card(self, ctx):
        """检定结束：远古印记投入的卡牌进入弃牌堆。"""
        if self._committed_card is None:
            return
        card_id = self._committed_card
        self._committed_card = None
        self._committed_icons = 0
        inv = self._get_mandy(ctx.game_state, ctx.investigator_id)
        if inv is None:
            return
        inv.discard.append(card_id)
