"""Dark Pact (Level 0) — Neutral Event, Basic Weakness. (Campaign Mode only)
对你所在地点的1名调查员造成2点伤害。
强制 - 当游戏结束或你被淘汰时，若黑暗契约仍在你的手牌中：将黑暗契约从
你的牌组中移除。从牌库收藏中找出失败的代价并加入你的牌组。

简化说明：
- 打出时目标自动选持有者自己（官方可选所在地点任意调查员）。
- 游戏结束/被淘汰的强制效果由 game_end_penalty() 提供给会话层结算
  （引擎无 GAME_ENDS 事件，同 cover_up 的 game_end_penalty 惯例）；
  "从牌组移除"记入 scenario.vars["removed_from_game"]。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class DarkPact(CardImplementation):
    card_id = "dark_pact_lv0"

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.AFTER)
    def deal_damage(self, ctx):
        """打出时：对你所在地点的1名调查员造成2点伤害（自动选自己）。"""
        if ctx.extra.get("card_id") != "dark_pact_lv0":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        inv.damage += 2  # 直接伤害（不分配）
        ctx.extra["dark_pact_damage"] = 2
        ctx.game_state.log_effect("🩸 黑暗契约：受到2点伤害")

    def game_end_penalty(self, game_state, investigator_id) -> str | None:
        """游戏结束/被淘汰结算：黑暗契约仍在手牌则移除并加入失败的代价。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or "dark_pact_lv0" not in inv.hand:
            return None
        inv.hand.remove("dark_pact_lv0")
        game_state.scenario.vars.setdefault(
            "removed_from_game", []).append("dark_pact_lv0")
        inv.deck.append("the_price_of_failure_lv0")
        return "黑暗契约仍在手牌：移除并加入失败的代价"
