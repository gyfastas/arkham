"""Protective Incantation (Level 1) — Mystic Asset, Arcane slot. (Blessed)
场上限制2张守护咒文。
封印（任意，[auto_fail]除外）。
强制 - 你的回合结束时：你必须花费1资源，否则弃掉守护咒文。

简化说明：
- 封印目标无选择 UI：入场时自动封印袋中对玩家最不利的标记（数值修正最低者；
  [auto_fail] 不可选；场景相关符号标记按0估值）。可用 seal_token 参数指定。
- 回合结束自动支付1资源（有则扣）；无资源时自动弃置本卡并释放封印标记。
- 离场（含被弃）时封印标记释放回袋。
- 混沌袋经 bind_chaos_bag() 注入（registry.activate_card 自动接线）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import (
    CHAOS_TOKEN_VALUES, ChaosTokenType, GameEvent, TimingPriority,
)


def _token_value(token) -> int:
    if token == ChaosTokenType.AUTO_FAIL:
        return -999
    return CHAOS_TOKEN_VALUES.get(token) or 0


class ProtectiveIncantation(CardImplementation):
    card_id = "protective_incantation_lv1"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._chaos_bag = None
        self._sealed_token = None

    def bind_chaos_bag(self, chaos_bag) -> None:
        self._chaos_bag = chaos_bag

    @on_event(GameEvent.CARD_ENTERS_PLAY, priority=TimingPriority.AFTER)
    def seal_on_enter(self, ctx):
        """入场：封印1个标记（默认袋中最不利者，auto_fail 除外）。"""
        if ctx.target != self.instance_id or self._chaos_bag is None:
            return
        chosen = ctx.extra.get("seal_token")
        candidates = [t for t in self._chaos_bag.tokens
                      if t != ChaosTokenType.AUTO_FAIL]
        if not candidates:
            return
        token = None
        if chosen is not None:
            try:
                token = ChaosTokenType(chosen)
            except ValueError:
                token = None
        if token is None or token not in candidates:
            token = min(candidates, key=_token_value)
        if self._chaos_bag.seal_token(token):
            self._sealed_token = token
            ctx.extra["protective_incantation_sealed"] = token.value

    @on_event(GameEvent.INVESTIGATOR_TURN_ENDS, priority=TimingPriority.FORCED)
    def pay_or_discard(self, ctx):
        """强制 - 你的回合结束时：花1资源，否则弃掉本卡。"""
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        if inv.resources >= 1:
            inv.resources -= 1
            ctx.extra["protective_incantation_paid"] = True
            return
        self._discard_self(ctx.game_state, inv)
        ctx.extra["protective_incantation_discarded"] = True

    @on_event(GameEvent.CARD_LEAVES_PLAY, priority=TimingPriority.AFTER)
    def release_on_leave(self, ctx):
        """离场：释放封印标记回袋。"""
        if ctx.target != self.instance_id:
            return
        self._release()

    def _release(self) -> None:
        if self._sealed_token is not None and self._chaos_bag is not None:
            self._chaos_bag.release_token(self._sealed_token)
        self._sealed_token = None

    def _discard_self(self, game_state, inv) -> None:
        """无资源支付时弃置本卡（镜像引擎资产移除流程，事件不补发）。"""
        from backend.engine.slots import vacate_asset_slots

        self._release()
        inst = game_state.get_card_instance(self.instance_id)
        vacate_asset_slots(game_state, self.instance_id)
        if self.instance_id in inv.play_area:
            inv.play_area.remove(self.instance_id)
        if inst is not None:
            inv.discard.append(inst.card_id)
        game_state.cards_in_play.pop(self.instance_id, None)
