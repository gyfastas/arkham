"""Promise of Power (Level 0) — Mystic Skill. (4 wild icons)
在你将力量诺言投入一次技能检定后，向混乱袋中加入1个[curse]标记。
若不能，改为受到2点恐惧。

简化说明：
- "若不能"按官方上限规则判定：袋中（含封印区）[curse]标记已达10个时
  无法再加入，改为受2恐惧。
- 混沌袋经 bind_chaos_bag() 注入（registry.activate_card 自动接线）；
  未绑定时跳过加标记（视为不能→受恐惧）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import ChaosTokenType, GameEvent, TimingPriority

MAX_CURSE_TOKENS = 10


class PromiseOfPower(CardImplementation):
    card_id = "promise_of_power_lv0"
    commit_effect_cost = 0
    commit_effect_label = "投入后向混乱袋加入1个[curse]标记"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._chaos_bag = None

    def bind_chaos_bag(self, chaos_bag) -> None:
        self._chaos_bag = chaos_bag

    @on_event(GameEvent.SKILL_TEST_COMMIT, priority=TimingPriority.WHEN)
    def add_curse(self, ctx):
        if self.card_id not in (ctx.committed_cards or []):
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        bag = self._chaos_bag
        existing = 0
        if bag is not None:
            existing = sum(1 for t in bag.tokens + bag.sealed
                           if t == ChaosTokenType.CURSE)
        if bag is not None and existing < MAX_CURSE_TOKENS:
            bag.add_token(ChaosTokenType.CURSE)
            ctx.extra["promise_of_power_curse_added"] = True
        else:
            inv.horror += 2
            ctx.extra["promise_of_power_horror"] = 2
