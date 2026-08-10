"""Token of Faith (Level 0) — Survivor Asset, Accessory slot. (07033)
[reaction] 在抽出了至少1个 [curse] 或 [auto_fail] 标记的技能检定结束后，
消耗宗教信物：加入同等数量的 [bless] 标记到混乱袋。

简化说明：
- 反应能力自动触发（官方为玩家选择是否消耗）：本卡在场且准备好的前提下，
  任何调查员的检定中每抽出1个诅咒/自动失败标记，检定结束时自动消耗并加入
  同等数量祝福标记。
- 混沌袋经 bind_chaos_bag 注入（registry 入场激活时接线；未绑定则不触发）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import ChaosTokenType, GameEvent, TimingPriority

_BAD = {ChaosTokenType.CURSE, ChaosTokenType.AUTO_FAIL}


class TokenOfFaith(CardImplementation):
    card_id = "token_of_faith_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._bad_tokens = 0

    def bind_chaos_bag(self, chaos_bag) -> None:
        """注入混沌袋（registry.activate_card / 测试接线）。"""
        self._chaos_bag = chaos_bag

    def _in_play_ready(self, game_state) -> bool:
        inst = game_state.get_card_instance(self.instance_id)
        return inst is not None and not inst.exhausted

    @on_event(GameEvent.CHAOS_TOKEN_REVEALED, priority=TimingPriority.AFTER)
    def count_bad_tokens(self, ctx):
        """统计本次检定抽出的诅咒/自动失败标记。"""
        if not self._in_play_ready(ctx.game_state):
            return
        if ctx.chaos_token in _BAD:
            self._bad_tokens += 1

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def add_bless_tokens(self, ctx):
        """检定结束：消耗本卡，加入同等数量祝福标记。"""
        try:
            if self._bad_tokens <= 0:
                return
            bag = getattr(self, "_chaos_bag", None)
            inst = ctx.game_state.get_card_instance(self.instance_id)
            if bag is None or inst is None or inst.exhausted:
                return
            inst.exhausted = True
            for _ in range(self._bad_tokens):
                bag.add_token(ChaosTokenType.BLESS)
            ctx.extra["token_of_faith_bless"] = self._bad_tokens
            ctx.game_state.log_effect(
                f"📿 宗教信物：消耗，加入{self._bad_tokens}个祝福标记")
        finally:
            self._bad_tokens = 0
