"""Heavy Furs (Level 0) — Neutral Asset, Body slot.
[reaction] 在你进行的技能检定中，当你揭示一个非[auto_fail]的符号标记后，
对厚重毛皮造成1点伤害：取消该混沌标记并将其放回袋中。揭示一个新标记。

简化说明：
- [reaction] 的时机选择实现为公开方法 activate()（先对毛皮造成1点伤害并
  武装），由会话层调用；武装后下一次 CHAOS_TOKEN_RESOLVED 若标记为
  非 auto_fail 符号（skull/cultist/tablet/elder_thing/frost）则取消并重抽。
- 引擎 ChaosBag.draw() 不移出标记，故"放回袋中"为无操作（标记本就在袋里）。
- 新标记在结算步生效：modifier 经 ctx.modify_amount 修正，新抽出 auto_fail
  时经 force_auto_fail 通道处理。
- 对毛皮的致命伤害作为费用支付后效果仍结算（官方允许）。
"""

from backend.cards._shared import defeat_asset
from backend.cards.base import CardImplementation, on_event
from backend.models.enums import (
    CHAOS_TOKEN_VALUES, ChaosTokenType, GameEvent, TimingPriority,
)

_SYMBOL_TOKENS = {
    ChaosTokenType.SKULL, ChaosTokenType.CULTIST, ChaosTokenType.TABLET,
    ChaosTokenType.ELDER_THING, ChaosTokenType.FROST,
}


class HeavyFurs(CardImplementation):
    card_id = "heavy_furs_lv0"
    activations = [{
        "id": "cancel_token",
        "label": "【响应】对毛皮造成1伤害：取消符号标记并重抽",
        "method": "activate",
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

    def activate(self, game_state, investigator_id) -> bool:
        """支付费用：对厚重毛皮造成1点伤害，武装一次标记取消。"""
        inst = game_state.get_card_instance(self.instance_id)
        inv = game_state.get_investigator(investigator_id)
        if inst is None or inv is None or self.instance_id not in inv.play_area:
            return False
        if self._armed:
            return False
        inst.damage += 1
        self._armed = True
        data = game_state.get_card_data(inst.card_id)
        if data is not None and data.health is not None \
                and inst.damage >= data.health:
            defeat_asset(game_state, self._bus, self.instance_id)
        return True

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.WHEN)
    def cancel_symbol_token(self, ctx):
        if not self._armed:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        token = ctx.chaos_token
        if token not in _SYMBOL_TOKENS:
            return  # 非符号标记：保持武装
        self._armed = False
        if self._bag is None or not self._bag.tokens:
            # 无混沌袋注入时的退化处理：仅取消修正
            ctx.modify_amount(-(ctx.amount or 0), "heavy_furs_cancel")
            return
        new_token = self._bag.draw()
        ctx.chaos_token = new_token  # 信息性记录（引擎以 modifier 为准）
        if new_token == ChaosTokenType.AUTO_FAIL:
            ctx.extra["force_auto_fail"] = True
            ctx.modify_amount(-(ctx.amount or 0), "heavy_furs_redraw")
        else:
            new_val = CHAOS_TOKEN_VALUES.get(new_token) or 0
            ctx.modify_amount(new_val - (ctx.amount or 0), "heavy_furs_redraw")
        ctx.game_state.log_effect(
            f"🧥 厚重毛皮：取消 {token.value} 标记，重新揭示 {new_token.value}"
        )

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._armed = False
