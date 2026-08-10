"""Three Aces (Level 1) — Rogue Skill. (06199)
多重。
如果你将3张三条A投入到一次技能检定，该次检定自动成功（不要从混乱袋抽出
混乱标记）。然后，抽取3张卡牌并获得3资源（本效果每次检定最多一次）。

简化说明：
- "自动成功"：投入3张时在 SKILL_TEST_COMMIT 将难度设为0（引擎
  ST.6 难度0即自动成功，同 double_or_nothing 的难度改写通道）；
  引擎仍会揭示标记（官方不揭示），若揭示到 auto_fail 则经
  ctx.extra["cancel_auto_fail"] 通道取消（同 eucatastrophe）。
- 奖励（抽3张+3资源）经 ctx.extra 标记协调，3份实现实例仅结算一次
  （"每次检定最多一次"）。
- "多重"（牌组可含3张以上）为牌组构建规则，引擎无校验通道（引擎缺口）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority

_COPIES_NEEDED = 3
_REWARD_CARDS = 3
_REWARD_RESOURCES = 3


class ThreeAces(CardImplementation):
    card_id = "three_aces_lv1"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._fired = False

    @on_event(GameEvent.SKILL_TEST_COMMIT, priority=TimingPriority.WHEN)
    def auto_success(self, ctx):
        """投入3张：难度设为0（自动成功，不揭示标记——引擎仍揭示，见类注释）。"""
        if ctx.committed_cards.count(self.card_id) < _COPIES_NEEDED:
            return
        ctx.difficulty = 0
        self._fired = True
        ctx.extra["three_aces_auto_success"] = True
        ctx.game_state.log_effect("🂡 三条A：投入3张，检定自动成功")

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.WHEN)
    def cancel_auto_fail_token(self, ctx):
        """自动成功不揭示标记：取消 auto_fail 标记的强制失败。"""
        if self._fired:
            ctx.extra["cancel_auto_fail"] = True

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.AFTER)
    def reward(self, ctx):
        """然后：抽3张牌并获得3资源（每次检定最多一次）。"""
        if not self._fired or ctx.extra.get("three_aces_rewarded"):
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        ctx.extra["three_aces_rewarded"] = True
        drawn = 0
        for _ in range(_REWARD_CARDS):
            if inv.deck:
                inv.hand.append(inv.deck.pop(0))
                drawn += 1
        inv.resources += _REWARD_RESOURCES
        ctx.extra["three_aces_drawn"] = drawn
        ctx.game_state.log_effect(f"🂡 三条A：抽{drawn}张牌，获得{_REWARD_RESOURCES}资源")

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._fired = False
