"""Another Day, Another Dollar (Level 3) — Rogue Asset. (05278)
永久。
你每场游戏开始时拥有额外2资源。

简化说明：
- "永久"（开局即入场，不占牌组）为牌组构建/开局规则，由会话层在设置阶段
  放入场上；本实现在其入场时（CARD_ENTERS_PLAY）一次性给予+2资源。
- 一次性标记在 impl 实例上；永久卡整局在场，实例不重建，不会重复触发。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class AnotherDayAnotherDollar(CardImplementation):
    card_id = "another_day_another_dollar_lv3"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._granted = False

    @on_event(GameEvent.CARD_ENTERS_PLAY, priority=TimingPriority.AFTER)
    def grant_starting_resources(self, ctx):
        """入场（开局设置）：额外获得2资源（一次性）。"""
        if ctx.target != self.instance_id or self._granted:
            return
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None:
            return
        inv = ctx.game_state.get_investigator(inst.owner_id)
        if inv is None:
            return
        self._granted = True
        inv.resources += 2
        ctx.game_state.log_effect("💼 干一天活计拿一天钱：开局额外获得2资源")

    def apply_game_start(self, game_state, investigator_id: str) -> bool:
        """开局奖励的公开入口（会话层设置阶段未发 CARD_ENTERS_PLAY 时调用）。"""
        if self._granted:
            return False
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return False
        self._granted = True
        inv.resources += 2
        game_state.log_effect("💼 干一天活计拿一天钱：开局额外获得2资源")
        return True
