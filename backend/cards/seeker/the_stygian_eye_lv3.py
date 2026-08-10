"""The Stygian Eye (Level 3) — Seeker Event, Fast. (07263)
快速。只能在你的回合中打出。
混乱袋内每有一个[curse]标记，打出幽暗之眼的费用减1。
直到本轮结束，你的每项技能+3。

简化说明：
- 费用减免在引擎出牌流程中无钩子（引擎按打印费用收取，引擎缺口）；
  提供 current_cost(chaos_bag) 供会话层结算费用（打印10 − 袋中诅咒数，
  下限0）；
- +3 全技能在 SKILL_VALUE_DETERMINED 对持有者生效，ROUND_ENDS 过期
  （事件临时实现同时由引擎在 ROUND_ENDS 自动注销）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import ChaosTokenType, GameEvent, TimingPriority

_PRINTED_COST = 10


class TheStygianEye(CardImplementation):
    card_id = "the_stygian_eye_lv3"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._owner_id: str | None = None

    @staticmethod
    def current_cost(chaos_bag) -> int:
        """混乱袋内每有1个诅咒标记，费用减1（下限0）。"""
        curses = sum(1 for t in chaos_bag.tokens if t == ChaosTokenType.CURSE)
        return max(0, _PRINTED_COST - curses)

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def arm(self, ctx):
        if ctx.extra.get("card_id") != self.card_id:
            return
        self._owner_id = ctx.investigator_id
        ctx.extra["stygian_eye_armed"] = True
        ctx.game_state.log_effect("👁️ 幽暗之眼：本轮你的每项技能+3")

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def boost_all_skills(self, ctx):
        if self._owner_id is None or ctx.investigator_id != self._owner_id:
            return
        if ctx.skill_type is None:
            return
        ctx.modify_amount(3, "stygian_eye_boost")

    @on_event(GameEvent.ROUND_ENDS, priority=TimingPriority.AFTER)
    def expire(self, ctx):
        self._owner_id = None
