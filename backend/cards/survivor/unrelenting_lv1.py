"""Unrelenting (Level 1) — Survivor Skill. (07196)
每次检定最多投入1张。
在你投入不屈不挠到技能检定后，在混乱袋查找最多3个你选择的非 [auto_fail]
混乱标记，并将其封印在不屈不挠上。如果不屈不挠上封印的3个标记都是
"+1"、"0"、[bless] 和/或 [elder_sign] 标记，抽取2张卡牌。在这次检定结束后，
释放此处封印的所有标记。

简化说明：
- "你选择的标记"自动选择为袋中最差的3个非自动失败标记（数值最小优先，
  其次符号标记），即防守性用法；因此抽牌条件只在袋中最差的3个标记本身就
  全是 "+1"/"0"/[bless]/[elder_sign] 时才会满足（官方为玩家自选）。
- 封印期间本次检定不会抽到被封印的标记（引擎抽袋不移除标记，封印经
  seal_token 从袋中移除生效）；检定结束经 release_token 归还。
- 混沌袋经 bind_chaos_bag 注入（registry 在投入激活时接线；未绑定则不触发）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import (
    CHAOS_TOKEN_VALUES, ChaosTokenType, GameEvent, TimingPriority,
)

_GOOD = {
    ChaosTokenType.PLUS_1, ChaosTokenType.ZERO,
    ChaosTokenType.BLESS, ChaosTokenType.ELDER_SIGN,
}


class Unrelenting(CardImplementation):
    card_id = "unrelenting_lv1"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._sealed: list[ChaosTokenType] = []

    def bind_chaos_bag(self, chaos_bag) -> None:
        """注入混沌袋（registry.activate_card / 测试接线）。"""
        self._chaos_bag = chaos_bag

    @on_event(GameEvent.SKILL_TEST_COMMIT, priority=TimingPriority.AFTER)
    def seal_tokens(self, ctx):
        """投入后：从袋中封印至多3个非自动失败标记（自动选最差的）。"""
        if self.card_id not in (ctx.committed_cards or []):
            return
        bag = getattr(self, "_chaos_bag", None)
        if bag is None:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)

        candidates = [t for t in bag.tokens if t != ChaosTokenType.AUTO_FAIL]
        # 数值标记按修正值排序（越小越差）；远古印记视为最佳，其余符号标记
        # 视为与 -3 同档
        def _rank(t) -> int:
            v = CHAOS_TOKEN_VALUES.get(t)
            if v is not None:
                return v
            if t == ChaosTokenType.ELDER_SIGN:
                return 3
            return -3

        candidates.sort(key=_rank)
        for token in candidates[:3]:
            if bag.seal_token(token):
                self._sealed.append(token)

        if self._sealed:
            names = "、".join(t.value for t in self._sealed)
            ctx.game_state.log_effect(f"🔒 不屈不挠：封印 {names}")
        ctx.extra["unrelenting_sealed"] = [t.value for t in self._sealed]

        # 封足3个且全是好标记：抽2张牌
        if (
            inv is not None
            and len(self._sealed) == 3
            and all(t in _GOOD for t in self._sealed)
        ):
            drawn = 0
            for _ in range(2):
                if inv.deck:
                    inv.hand.append(inv.deck.pop(0))
                    drawn += 1
            ctx.extra["unrelenting_drawn"] = drawn
            ctx.game_state.log_effect(f"🔒 不屈不挠：封印全为良标记，抽{drawn}张牌")

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def release_tokens(self, ctx):
        """检定结束：释放此处封印的所有标记。"""
        if not self._sealed:
            return
        bag = getattr(self, "_chaos_bag", None)
        if bag is not None:
            for token in self._sealed:
                bag.release_token(token)
        ctx.extra["unrelenting_released"] = [t.value for t in self._sealed]
        self._sealed = []
