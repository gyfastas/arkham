"""Gregory Gry (Level 0) — Rogue Asset, Ally slot. (06162)
使用(9资源)。
[反应]当你发起技能检定时，从格雷戈里·格赖上花费至多3资源：若本次检定
成功且超出难度至少该数量，获得等量资源。

简化说明：
- "花费至多3资源"需玩家选择数量：spend(amount) 公开方法（1-3，受卡上
  资源标记数限制），由 UI/会话层在发起检定时调用。
- 数据 uses 键兼容双 s 写法（"resourcess"）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority

_MAX_WAGER = 3


def _uses_key(inst, key: str) -> str:
    """兼容源数据复数化笔误（"resourcess"）。"""
    if key in inst.uses:
        return key
    alt = f"{key}s"
    return alt if alt in inst.uses else key


class GregoryGry(CardImplementation):
    card_id = "gregory_gry_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._wagered = 0

    def spend(self, game_state, investigator_id: str, amount: int = 1) -> bool:
        """从本卡花费1-3资源：检定成功超出难度至少该数量则返还等量资源。"""
        if amount < 1 or amount > _MAX_WAGER:
            return False
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None:
            return False
        key = _uses_key(inst, "resources")
        if inst.uses.get(key, 0) < amount:
            return False
        inst.uses[key] -= amount
        self._wagered = amount
        return True

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.AFTER)
    def payout(self, ctx):
        """成功且超出难度至少花费数量：获得等量资源。"""
        if not self._wagered:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        margin = (ctx.modified_skill or 0) - (ctx.difficulty or 0)
        if margin < self._wagered:
            return
        inv.resources += self._wagered
        ctx.extra["gregory_gry_payout"] = self._wagered
        ctx.game_state.log_effect(
            f"🪙 格雷戈里·格赖：押注{self._wagered}资源成功，返还{self._wagered}资源")

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._wagered = 0
