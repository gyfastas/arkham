"""Eldritch Inspiration (Level 0) — Mystic Event. (05033)
快速。在你将要结算一张[mystic]卡牌的效果，且该效果在揭示[skull]、[cultist]、
[tablet]、[elder_thing]或[auto_fail]符号时/如果揭示/在揭示后触发时打出。
取消该效果，或额外结算一次该效果。

简化说明：
- 从手牌中自动触发（同 a_test_of_will 惯例）：你的检定揭示上述符号时，
  若手牌中有恐怖灵感（0费），自动打出。
- 取消/双倍无通用重结算通道（各卡符号效果分散在各自 AFTER 处理器中，
  引擎无"效果重放/否决"机制——引擎缺口）：本实现将模式写入
  scenario.vars["eldritch_inspiration"]（默认 "double"，会话层可经
  pending_mode 属性预设 "cancel"），供各 mystic 卡的符号触发效果查询；
  并记录 ctx.extra["eldritch_inspiration_token"] 标明作用标记。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import ChaosTokenType, GameEvent, TimingPriority

_TRIGGER_SYMBOLS = {
    ChaosTokenType.SKULL, ChaosTokenType.CULTIST,
    ChaosTokenType.TABLET, ChaosTokenType.ELDER_THING,
    ChaosTokenType.AUTO_FAIL,
}

VAR_KEY = "eldritch_inspiration"


class EldritchInspiration(CardImplementation):
    card_id = "eldritch_inspiration_lv0"
    persistent_in_hand = True  # 在手牌中持续监听符号揭示窗口

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._spent = False
        # 会话层可在揭示前预设："cancel" 或 "double"（默认）
        self.pending_mode = "double"

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.WHEN)
    def play_on_symbol(self, ctx):
        if self._spent or ctx.chaos_token not in _TRIGGER_SYMBOLS:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.card_id not in inv.hand:
            return

        # 0费：直接打出
        inv.hand.remove(self.card_id)
        inv.discard.append(self.card_id)
        self._spent = True

        mode = self.pending_mode if self.pending_mode in ("cancel", "double") else "double"
        ctx.game_state.scenario.vars[VAR_KEY] = {
            "investigator_id": inv.investigator_id,
            "mode": mode,
            "token": ctx.chaos_token.value,
        }
        ctx.extra["eldritch_inspiration_played"] = mode
        ctx.game_state.log_effect(
            f"🌀 恐怖灵感：{'取消' if mode == 'cancel' else '额外结算一次'}"
            f"本标记触发的法术效果")

    @staticmethod
    def consume_mode(game_state, investigator_id: str) -> str | None:
        """符号触发效果查询并消费本次灵感模式（"cancel"/"double"/None）。"""
        entry = game_state.scenario.vars.get(VAR_KEY)
        if not entry or entry.get("investigator_id") != investigator_id:
            return None
        game_state.scenario.vars.pop(VAR_KEY, None)
        return entry.get("mode")
