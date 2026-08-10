""""Watch this!" (Level 0) — Rogue Skill.
只能投入你正在进行的技能检定。将"吃我一招！"投入技能检定时，
花费最多3资源作为额外费用。
如果你成功且超出难度至少1点，获得花费数量两倍的资源。

简化说明：
- "花费最多3资源"简化为自动花费 min(3, 当前资源)
  （最有利/最常用分支：成功超1即翻倍返还，满注是占优策略；
  引擎的 commit_effect_cost 仅支持固定整数，不支持可变费用）。
- "只能投入你正在进行的技能检定"：本引擎检定始终由执行者本人投入，
  多人局替他人投入的限制未实现（引擎缺口）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority

_MAX_WAGER = 3


class WatchThis(CardImplementation):
    card_id = "watch_this_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._wagered = 0

    @on_event(GameEvent.SKILL_TEST_COMMIT, priority=TimingPriority.WHEN)
    def pay_wager(self, ctx):
        """投入时：花费最多3资源作为额外费用。"""
        if "watch_this_lv0" not in ctx.committed_cards:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        wager = min(_MAX_WAGER, inv.resources)
        if wager <= 0:
            return
        inv.resources -= wager
        self._wagered = wager
        ctx.extra["watch_this_wager"] = wager

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.AFTER)
    def double_payout(self, ctx):
        """成功且超出难度至少1点：获得花费数量两倍的资源。"""
        if not self._wagered:
            return
        margin = (ctx.modified_skill or 0) - (ctx.difficulty or 0)
        if margin < 1:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        payout = 2 * self._wagered
        inv.resources += payout
        ctx.extra["watch_this_payout"] = payout
        ctx.game_state.log_effect(
            f"👀 吃我一招！：押注{self._wagered}资源，成功返还{payout}")

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._wagered = 0
