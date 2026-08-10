"""Fey (Level 1) — Seeker Skill. (07222)
如果这次技能检定中抽出[curse]标记，在这次检定结束时，你可以将鬼灵精怪
返回你的手牌。

简化说明：
- "你可以"为自动触发（官方为玩家选择；与 lucky 等卡的自动简化一致）；
- 投入的技能卡实例在 ST.2 激活，CHAOS_TOKEN_RESOLVED 记录诅咒标记，
  SKILL_TEST_ENDS（ST.8 投入卡已入弃牌堆后）将本卡从弃牌堆拿回手牌。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import ChaosTokenType, GameEvent, TimingPriority


class Fey(CardImplementation):
    card_id = "fey_lv1"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._committed_by: str | None = None
        self._curse_revealed = False

    @on_event(GameEvent.SKILL_TEST_COMMIT, priority=TimingPriority.AFTER)
    def track_commit(self, ctx):
        if self.card_id in (ctx.committed_cards or []):
            self._committed_by = ctx.investigator_id
            self._curse_revealed = False

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.AFTER)
    def track_curse(self, ctx):
        if self._committed_by is not None and ctx.chaos_token == ChaosTokenType.CURSE:
            self._curse_revealed = True

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def return_to_hand(self, ctx):
        """检定中揭示了诅咒标记：本卡从弃牌堆返回手牌。"""
        inv_id, self._committed_by = self._committed_by, None
        if inv_id is None or not self._curse_revealed:
            return
        self._curse_revealed = False
        inv = ctx.game_state.get_investigator(inv_id)
        if inv is None or self.card_id not in inv.discard:
            return
        inv.discard.remove(self.card_id)
        inv.hand.append(self.card_id)
        ctx.extra["fey_returned"] = True
        ctx.game_state.log_effect("🧚 鬼灵精怪：揭示了诅咒标记，返回手牌")
