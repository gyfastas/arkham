"""Paradoxical Covenant (Level 2) — Mystic Asset, Permanent. (Blessed/Cursed)
永久。牌组限制1张[[誓约]]。
[reaction] 你所在地点的一位调查员执行技能检定的"揭示混沌标记"步骤后，
如果该次检定中既揭示了[bless]标记又揭示了[curse]标记，横置悖论誓约：
本次检定自动成功。（本次检定结束后，将从混乱袋移除揭示的每个[bless]和
[curse]标记。）

简化说明：
- 多标记揭示只会在 Olive McBride 等效果下发生；本实现跨整次检定的
  CHAOS_TOKEN_RESOLVED 追踪两种标记是否都出现过。
- 自动成功经 SKILL_TEST_FAILED 翻转 ctx.success（同 lucky 通道）。
- 检定结束后从袋中移除本次揭示的祝福/诅咒标记（bind_chaos_bag 注入）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import ChaosTokenType, GameEvent, TimingPriority


class ParadoxicalCovenant(CardImplementation):
    card_id = "paradoxical_covenant_lv2"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._chaos_bag = None
        self._revealed: list[ChaosTokenType] = []
        self._auto_succeed = False

    def bind_chaos_bag(self, chaos_bag) -> None:
        self._chaos_bag = chaos_bag

    def _ready_in_play(self, game_state, investigator_id) -> bool:
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        return (
            inst is not None and not inst.exhausted
            and self.instance_id in inv.play_area
        )

    def _tester_at_owner_location(self, ctx) -> bool:
        owner = ctx.game_state.get_investigator(
            getattr(ctx.game_state.get_card_instance(self.instance_id),
                    "owner_id", None))
        tester = ctx.game_state.get_investigator(ctx.investigator_id)
        return (owner is not None and tester is not None
                and owner.location_id == tester.location_id)

    @on_event(GameEvent.SKILL_TEST_BEGINS, priority=TimingPriority.AFTER)
    def reset_tracking(self, ctx):
        self._revealed = []
        self._auto_succeed = False

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.AFTER)
    def track_bless_curse(self, ctx):
        if not self._ready_in_play(ctx.game_state, ctx.investigator_id):
            return
        if not self._tester_at_owner_location(ctx):
            return
        if ctx.chaos_token in (ChaosTokenType.BLESS, ChaosTokenType.CURSE):
            self._revealed.append(ctx.chaos_token)
        if (ChaosTokenType.BLESS in self._revealed
                and ChaosTokenType.CURSE in self._revealed):
            inst = ctx.game_state.get_card_instance(self.instance_id)
            inst.exhausted = True
            self._auto_succeed = True
            ctx.extra["paradoxical_covenant_triggered"] = True

    @on_event(GameEvent.SKILL_TEST_FAILED, priority=TimingPriority.WHEN)
    def auto_succeed(self, ctx):
        if self._auto_succeed and self._tester_at_owner_location(ctx):
            ctx.success = True
            ctx.extra["paradoxical_covenant_auto_success"] = True

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def remove_tokens(self, ctx):
        """检定结束后：从袋中移除本次揭示的每个[bless]/[curse]。"""
        if self._auto_succeed and self._chaos_bag is not None:
            for token in self._revealed:
                self._chaos_bag.remove(token)
        self._revealed = []
        self._auto_succeed = False
