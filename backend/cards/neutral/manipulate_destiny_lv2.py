"""Manipulate Destiny (Level 2) — Neutral Event.
从混沌袋中揭示标记，直到揭示一个[curse]、[auto_fail]、[bless]或
[elder_sign]标记。若揭示的是…
- …[curse]或[auto_fail]标记，对你所在地点的1名敌人造成2点伤害。
- …[bless]或[elder_sign]标记，治愈你所在地点1位调查员或[[Ally]]支援的
  2点伤害。
本行动不引发借机攻击。

简化说明：
- 目标选择：敌人默认优先与你交战者，其次地点未交战列表首位；治愈默认
  本人，可用 ctx.extra["target_investigator"] 指定（须同地点）；Ally 治愈
  未实现（注明）。
- 揭示期间标记临时移出袋（模拟"放到一旁"），效果结算后全部放回
  （官方对非检定揭示的 bless/curse 也是结算后即放回）。
- "不引发借机攻击"：CARD_PLAYED 在行动结算的 AoO 之前触发，故举盾取消
  本次打牌的 ATTACK_OF_OPPORTUNITY。
- 混沌袋经 bind_chaos_bag() 注入。
"""

from backend.cards._shared import deal_damage_to_enemy
from backend.cards.base import CardImplementation, on_event
from backend.models.enums import ChaosTokenType, GameEvent, TimingPriority

_STOP_TOKENS = {
    ChaosTokenType.CURSE, ChaosTokenType.AUTO_FAIL,
    ChaosTokenType.BLESS, ChaosTokenType.ELDER_SIGN,
}


class ManipulateDestiny(CardImplementation):
    card_id = "manipulate_destiny_lv2"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._bag = None
        self._bus = None
        self._aoo_shield = False

    def bind_chaos_bag(self, chaos_bag) -> None:
        self._bag = chaos_bag

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def reveal_tokens(self, ctx):
        if ctx.extra.get("card_id") != "manipulate_destiny_lv2":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        self._aoo_shield = True  # 本行动不引发借机攻击
        bag = self._bag
        if bag is None or not bag.tokens:
            return

        # 揭示直到命中停止标记（揭示的标记临时移出袋）
        revealed: list[ChaosTokenType] = []
        stop_token = None
        while bag.tokens:
            token = bag.draw()
            bag.remove(token)
            revealed.append(token)
            if token in _STOP_TOKENS:
                stop_token = token
                break
        # 结算后所有揭示的标记放回袋中
        for token in revealed:
            bag.return_token(token)

        if stop_token is None:
            ctx.game_state.log_effect("🔮 操纵命运：袋中无可停下的标记")
            return

        if stop_token in (ChaosTokenType.CURSE, ChaosTokenType.AUTO_FAIL):
            enemy_iid = self._pick_enemy(ctx.game_state, inv)
            if enemy_iid is not None:
                deal_damage_to_enemy(
                    ctx.game_state, self._bus, enemy_iid, 2,
                    defeated_by=inv.investigator_id,
                )
                ctx.game_state.log_effect(
                    f"🔮 操纵命运：揭示 {stop_token.value}，对敌人造成2点伤害"
                )
            else:
                ctx.game_state.log_effect("🔮 操纵命运：你所在地点没有敌人")
        else:
            target_id = ctx.extra.get("target_investigator") or inv.investigator_id
            target = ctx.game_state.get_investigator(target_id)
            if target is None or target.location_id != inv.location_id:
                target = inv
            healed = min(2, target.damage)
            target.damage -= healed
            ctx.game_state.log_effect(
                f"🔮 操纵命运：揭示 {stop_token.value}，"
                f"治愈 {target.investigator_id} {healed} 点伤害"
            )

    @on_event(GameEvent.ATTACK_OF_OPPORTUNITY, priority=TimingPriority.WHEN)
    def cancel_aoo(self, ctx):
        if self._aoo_shield:
            ctx.cancel()

    @on_event(GameEvent.ACTION_PERFORMED, priority=TimingPriority.AFTER)
    def drop_shield(self, ctx):
        self._aoo_shield = False

    @staticmethod
    def _pick_enemy(game_state, inv):
        for enemy_iid in inv.threat_area:
            return enemy_iid
        location = game_state.get_location(inv.location_id)
        if location is not None and location.enemies:
            return location.enemies[0]
        return None
