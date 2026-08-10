"""Lodge "Debts" (Level 0) — Neutral Event, Weakness.
将会所"欠款"移出游戏。
强制 - 当游戏结束或你被淘汰时，若会所"欠款"仍在你的手牌中：
你承受1点精神创伤。

简化说明：
- 引擎 _play_event 在 CARD_PLAYED 后无条件将事件置入弃牌堆，无法拦截；
  "移出游戏"记录于 scenario.vars["removed_from_game"]，会话层应以此为准
  （弃牌堆中的同名残留为已知偏差）。
- "游戏结束/被淘汰"无引擎事件（引擎缺口），实现为公开方法
  on_game_end()，由会话层在游戏结束或调查员被淘汰时调用。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class LodgeDebts(CardImplementation):
    card_id = "lodge_debts_lv0"

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def remove_from_game(self, ctx):
        if ctx.extra.get("card_id") != "lodge_debts_lv0":
            return
        ctx.game_state.scenario.vars.setdefault(
            "removed_from_game", []
        ).append("lodge_debts_lv0")
        ctx.game_state.log_effect("🏛️ 会所\"欠款\"：移出游戏")

    def on_game_end(self, game_state, investigator_id) -> bool:
        """游戏结束/被淘汰时若仍在手牌：承受1点精神创伤。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or "lodge_debts_lv0" not in inv.hand:
            return False
        card = getattr(inv, "investigator_card", None)
        if card is None:
            return False
        card.mental_trauma += 1
        game_state.log_effect("🏛️ 会所\"欠款\"：仍在手牌，承受1点精神创伤")
        return True
