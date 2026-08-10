"""21 or Bust (Level 0) — Rogue Event. (08048)
依次从混乱袋随机抽出标记，直到你选择停下。将每个[骷髅]、[异教徒]、[石板]
或[远古者]视为5；[自动失败]视为10；[远古印记]视为1或11。如果这些标记的
总和（忽略+/-）为……
- ……18或更少，获得4资源。
- ……19，获得5资源。
- ……20，获得6资源。
- ……21，获得9资源。

简化说明：
- "直到你选择停下"简化为自动策略：总和达到19及以上即停（超过21爆掉
  也停止），即始终冲击19/20/21档位；[远古印记]在总和≤10时计11，否则计1
  （最有利读法）。兜底：最多揭示15个标记即停（防止理论上的无限循环，
  官方由玩家自行决定停手）。
- 数字标记取绝对值（卡面"忽略+/-"）；[祝福]/[诅咒]/[冰霜]按面值绝对值计。
- 标记只是"揭示"，不移出混沌袋（ChaosBag.draw 本身不移除，规则上揭示后
  归还袋中）。
- 混沌袋经 bind_chaos_bag 注入（registry.activate_card 已接线；未注入则
  不结算）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import (
    CHAOS_TOKEN_VALUES, ChaosTokenType, GameEvent, TimingPriority,
)

_SYMBOL_FIVE = {
    ChaosTokenType.SKULL, ChaosTokenType.CULTIST,
    ChaosTokenType.TABLET, ChaosTokenType.ELDER_THING,
}

_PAYOUT = {19: 5, 20: 6, 21: 9}
_BASE_PAYOUT = 4  # 18或更少


class TwentyOneOrBust(CardImplementation):
    card_id = "21_or_bust_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._chaos_bag = None

    def bind_chaos_bag(self, chaos_bag) -> None:
        """注入游戏混沌袋（registry.activate_card 自动调用）。"""
        self._chaos_bag = chaos_bag

    @staticmethod
    def _token_value(token, current_total: int) -> int:
        if token in _SYMBOL_FIVE:
            return 5
        if token == ChaosTokenType.AUTO_FAIL:
            return 10
        if token == ChaosTokenType.ELDER_SIGN:
            return 11 if current_total <= 10 else 1
        value = CHAOS_TOKEN_VALUES.get(token)
        return abs(value) if value is not None else 0

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def push_your_luck(self, ctx):
        """自动揭示标记直到总和≥19（或爆掉），按总和结算资源。"""
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self._chaos_bag is None:
            return

        total = 0
        revealed: list[ChaosTokenType] = []
        while total < 19 and len(revealed) < 15:
            token = self._chaos_bag.draw()
            revealed.append(token)
            total += self._token_value(token, total)
            if total > 21:
                break

        gained = 0
        if total <= 21:
            gained = _PAYOUT.get(total, _BASE_PAYOUT)
            inv.resources += gained

        ctx.extra["21_or_bust"] = {
            "tokens": [t.value for t in revealed],
            "total": total,
            "gained": gained,
        }
        names = "、".join(t.value for t in revealed)
        if gained:
            ctx.game_state.log_effect(
                f"🎰 21点：揭示 {names}，合计{total}点，获得{gained}资源")
        else:
            ctx.game_state.log_effect(
                f"🎰 21点：揭示 {names}，合计{total}点——爆掉，一无所获")
