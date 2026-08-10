"""Priest of Two Faiths (Level 1) — Rogue Asset, Ally. (07156)
[reaction] 在双面神父入场后：加入3个[bless]标记到混乱袋。
强制 - 当结束补给阶段时：你必须加入1个[curse]标记到混乱袋或丢弃双面神父。

简化说明：
- 混沌袋经 bind_chaos_bag() 注入（registry.activate_card 自动接线，同
  keep_faith）；未绑定时效果落空。
- 补给阶段结束的强制二选一自动选择"加入1个诅咒标记"（保留神父是常见
  选择；丢弃分支需玩家选择 UI，未实现）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import ChaosTokenType, GameEvent, TimingPriority


class PriestOfTwoFaiths(CardImplementation):
    card_id = "priest_of_two_faiths_lv1"

    def bind_chaos_bag(self, chaos_bag) -> None:
        self._chaos_bag = chaos_bag

    @on_event(GameEvent.CARD_ENTERS_PLAY, priority=TimingPriority.REACTION)
    def add_bless_on_enter(self, ctx):
        """入场后：向混沌袋加入3个祝福标记。"""
        if ctx.target != self.instance_id:
            return
        bag = getattr(self, "_chaos_bag", None)
        if bag is None:
            return
        for _ in range(3):
            bag.add_token(ChaosTokenType.BLESS)
        ctx.extra["priest_bless_added"] = 3
        ctx.game_state.log_effect("⛪ 双面神父：向混沌袋加入3个祝福标记")

    @on_event(GameEvent.UPKEEP_PHASE_ENDS, priority=TimingPriority.FORCED)
    def forced_curse_or_discard(self, ctx):
        """强制 - 补给阶段结束时：加入1个诅咒标记（自动选择，保留神父）。"""
        owner = None
        for inv in ctx.game_state.investigators.values():
            if self.instance_id in inv.play_area:
                owner = inv
                break
        if owner is None:
            return
        bag = getattr(self, "_chaos_bag", None)
        if bag is None:
            return
        bag.add_token(ChaosTokenType.CURSE)
        ctx.extra["priest_curse_added"] = True
        ctx.game_state.log_effect("⛪ 双面神父：补给阶段结束，向混沌袋加入1个诅咒标记")
