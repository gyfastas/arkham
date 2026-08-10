"""Favor of the Moon (Level 1) — Neutral Asset.
快速。封印（至多3个[curse]）。若月之恩惠上没有封印的标记，丢弃之。
[reaction] 当你将从混沌袋中揭示一个混沌标记时，横置月之恩惠：
改为结算封印在此的1个标记，视同刚从混沌袋中揭示。然后获得1资源。

简化说明：
- [reaction] 的触发时机（"将要揭示时"）需玩家选择，实现为公开方法
  activate_resolve_sealed()（横置并武装），由会话层在检定揭示前调用；
  武装后下一次 CHAOS_TOKEN_RESOLVED 改为按封印标记（curse/-2）结算。
- 引擎 _st3_reveal 不回读 ctx.chaos_token，无法替换"被揭示的动画标记"，
  本卡在结算步修正 modifier（auto_fail 标记经 cancel_auto_fail 通道取消）。
- 封印数量记录在实例 uses["sealed"]；混沌袋经 bind_chaos_bag() 注入
  （registry.activate_card 自动接线）。
- 结算后封印标记释放回混沌袋；封印归零时丢弃本卡（含进场即封印0个的情况）。
"""

from backend.cards._shared import defeat_asset
from backend.cards.base import CardImplementation, on_event
from backend.models.enums import (
    CHAOS_TOKEN_VALUES, ChaosTokenType, GameEvent, TimingPriority,
)


class FavorOfTheMoon(CardImplementation):
    card_id = "favor_of_the_moon_lv1"
    token_type = ChaosTokenType.CURSE
    gain_resource = True  # Favor of the Sun 无此效果
    sealed_max = 3
    activations = [{
        "id": "resolve_sealed",
        "label": "【响应】横置：改为结算封印的标记（+1资源）",
        "method": "activate_resolve_sealed",
    }]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._bag = None
        self._bus = None
        self._armed = False

    def bind_chaos_bag(self, chaos_bag) -> None:
        self._bag = chaos_bag

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus

    @on_event(GameEvent.CARD_ENTERS_PLAY, priority=TimingPriority.AFTER)
    def seal_on_enter(self, ctx):
        """进场：从混沌袋封印至多3个[curse]；1个都封印不到则丢弃。"""
        if ctx.target != self.instance_id:
            return
        inst = ctx.game_state.get_card_instance(self.instance_id)
        sealed = 0
        if self._bag is not None:
            for _ in range(self.sealed_max):
                if self._bag.seal_token(self.token_type):
                    sealed += 1
        if inst is not None:
            inst.uses["sealed"] = sealed
        if sealed:
            ctx.game_state.log_effect(
                f"🌙 月之恩惠：封印 {sealed} 个 {self.token_type.value} 标记"
            )
        else:
            ctx.game_state.log_effect("🌙 月之恩惠：无可封印的标记，丢弃")
            defeat_asset(ctx.game_state, self._bus, self.instance_id)

    def activate_resolve_sealed(self, game_state, investigator_id) -> bool:
        """[reaction] 横置：下一次你揭示标记时改为结算封印的标记。"""
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None or inst.controller_id != investigator_id:
            return False
        if inst.exhausted or inst.uses.get("sealed", 0) <= 0:
            return False
        inst.exhausted = True
        self._armed = True
        return True

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.WHEN)
    def resolve_sealed_token(self, ctx):
        if not self._armed:
            return
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None or inst.controller_id != ctx.investigator_id:
            return
        self._armed = False
        if inst.uses.get("sealed", 0) <= 0:
            return
        inst.uses["sealed"] -= 1
        # 封印的标记释放回袋，并改为按它结算
        if self._bag is not None:
            self._bag.release_token(self.token_type)
        if ctx.chaos_token == ChaosTokenType.AUTO_FAIL:
            ctx.extra["cancel_auto_fail"] = True
        target = CHAOS_TOKEN_VALUES.get(self.token_type) or 0
        ctx.modify_amount(target - (ctx.amount or 0), f"{self.card_id}_sealed")
        ctx.chaos_token = self.token_type  # 信息性记录（引擎不回读）
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if self.gain_resource and inv is not None:
            inv.resources += 1
        ctx.game_state.log_effect(
            f"🌙 {ctx.game_state.card_name(self.card_id)}："
            f"改为结算封印的 {self.token_type.value} 标记"
        )
        if inst.uses.get("sealed", 0) <= 0:
            ctx.game_state.log_effect(
                f"🌙 {ctx.game_state.card_name(self.card_id)}：封印耗尽，丢弃"
            )
            defeat_asset(ctx.game_state, self._bus, self.instance_id)

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._armed = False
