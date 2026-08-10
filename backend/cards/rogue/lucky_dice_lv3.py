"""Lucky Dice (Level 3) — Rogue Asset. (07307)
卓绝。
[反应]当你揭示一枚非[curse]、非[auto_fail]的混沌标记时，向混沌袋加入
1个[curse]标记：无视刚揭示的标记，改为揭示另1枚标记结算。若该标记带有
[curse]或[auto_fail]符号，将幸运骰子返回你的手牌（无法被无视/取消）。

简化说明：
- 重抽通道同 grotesque_statue：直接改写本次检定的标记与修正；
  新标记的场景符号按0估值，[auto_fail]经 extra["force_auto_fail"]。
- 每次检定事件只重抽一次（引擎对新标记不再次发射事件，不连锁；
  官方对重抽出的非诅咒标记可再次触发，列为简化）。
- 返回手牌：从在场移除（释放槽位）并加入持有者手牌，不进弃牌堆。
- 混沌袋经 bind_chaos_bag() 注入；未绑定时不触发。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import (
    CHAOS_TOKEN_VALUES, ChaosTokenType, GameEvent, TimingPriority,
)


class LuckyDice(CardImplementation):
    card_id = "lucky_dice_lv3"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._bus = None
        self._chaos_bag = None

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus  # 返回手牌时需发射 CARD_LEAVES_PLAY

    def bind_chaos_bag(self, chaos_bag) -> None:
        """注入游戏混沌袋（registry.activate_card 自动调用）。"""
        self._chaos_bag = chaos_bag

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.WHEN)
    def reroll(self, ctx):
        if ctx.chaos_token in (ChaosTokenType.CURSE, ChaosTokenType.AUTO_FAIL):
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        if self._chaos_bag is None:
            return

        # 费用：向混沌袋加入1个[curse]标记
        self._chaos_bag.add_token(ChaosTokenType.CURSE)

        token = self._chaos_bag.draw()
        ctx.chaos_token = token
        new_value = CHAOS_TOKEN_VALUES.get(token) or 0
        ctx.modify_amount(new_value - (ctx.amount or 0), "lucky_dice_reroll")
        ctx.extra["lucky_dice_rerolled"] = token.value
        if token == ChaosTokenType.AUTO_FAIL:
            ctx.extra["force_auto_fail"] = True
        ctx.game_state.log_effect(
            f"🎲 幸运骰子：无视原标记，重抽为[{token.value}]")

        if token in (ChaosTokenType.CURSE, ChaosTokenType.AUTO_FAIL):
            self._return_to_hand(ctx, inv)

    def _return_to_hand(self, ctx, inv) -> None:
        """重抽出[curse]/[auto_fail]：本卡返回持有者手牌（不进弃牌堆）。"""
        from backend.engine.event_bus import EventContext
        slot_mgr = getattr(ctx.game_state, "slot_managers", {}).get(inv.investigator_id)
        if slot_mgr is not None:
            slot_mgr.vacate(self.instance_id)
        if self.instance_id in inv.play_area:
            inv.play_area.remove(self.instance_id)
        ctx.game_state.cards_in_play.pop(self.instance_id, None)
        inv.hand.append(self.card_id)
        ctx.extra["lucky_dice_returned"] = True
        ctx.game_state.log_effect("🎲 幸运骰子：返回手牌")
        if self._bus is not None:
            self._bus.emit(EventContext(
                game_state=ctx.game_state,
                event=GameEvent.CARD_LEAVES_PLAY,
                investigator_id=inv.investigator_id,
                target=self.instance_id,
                extra={"card_id": self.card_id},
            ))
