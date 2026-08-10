"""Toe to Toe (Level 0) — Guardian Event. (08020)
攻击。这次攻击造成+1伤害并自动成功。作为执行这次攻击的额外费用，
所选敌人攻击你。

简化说明：
- 目标：默认选你威胁区第一个敌人；可用 ctx.extra["enemy_instance_id"]
  指定你所在地点的敌人（含同地点其他调查员威胁区/地点上未交战的）。
- "敌人攻击你"（额外费用）：发出 ENEMY_ATTACKS（可被 Dodge 等取消）后
  经 DamageEngine 结算敌人卡面的伤害/恐惧（同 hoods_lv0 模式，可正常
  分配给支援卡）。即便攻击被取消，本次攻击效果仍结算（费用已支付）。
- "自动成功"：不发起技能检定，直接以 deal_damage_to_enemy 结算
  2点伤害（基础1+1，含击败流程，与 mano_a_mano_lv1 一致）。
- 本卡是 Fight 行动：打出不引起趁乱攻击（同 mano_a_mano 的一次性豁免）。
"""

from backend.cards._shared import deal_damage_to_enemy
from backend.cards.base import CardImplementation, on_event
from backend.engine.damage import DamageEngine
from backend.engine.event_bus import EventContext
from backend.models.enums import CardType, GameEvent, TimingPriority


class ToeToToe(CardImplementation):
    card_id = "toe_to_toe_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._bus = None
        self._aoo_free = None

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def fight(self, ctx):
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return

        target_iid = self._choose_target(ctx, inv)
        if target_iid is None:
            ctx.extra["toe_to_toe_fizzle"] = True
            ctx.game_state.log_effect("⚔️ 针锋相对：所在地点没有可攻击的敌人，效果不结算")
            return

        # 额外费用：所选敌人攻击你（可被 Dodge 等取消；取消不影响攻击结算）
        enemy_data = ctx.game_state.get_card_data(
            ctx.game_state.get_card_instance(target_iid).card_id)
        attack_ctx = EventContext(
            game_state=ctx.game_state,
            event=GameEvent.ENEMY_ATTACKS,
            investigator_id=inv.investigator_id,
            enemy_id=target_iid,
        )
        if self._bus is not None:
            self._bus.emit(attack_ctx)
        if attack_ctx.cancelled:
            ctx.game_state.log_effect("⚔️ 针锋相对：敌人的还击攻击被取消")
        else:
            DamageEngine(ctx.game_state, self._bus).deal_damage(
                inv.investigator_id,
                damage=enemy_data.enemy_damage or 0,
                horror=enemy_data.enemy_horror or 0,
                source=target_iid,
            )
            ctx.game_state.log_effect("⚔️ 针锋相对：所选敌人攻击你（额外费用）")

        # 攻击自动成功，造成 +1伤害（基础1 + 1 = 2）
        deal_damage_to_enemy(ctx.game_state, self._bus, target_iid, 2,
                             defeated_by=inv.investigator_id)
        ctx.extra["toe_to_toe_target"] = target_iid
        ctx.game_state.log_effect("⚔️ 针锋相对：攻击自动成功，造成2点伤害")

        # Fight 行动：打出不引起趁乱攻击
        self._aoo_free = inv.investigator_id

    def _choose_target(self, ctx, inv) -> str | None:
        """合法目标：你所在地点的敌人（你的/同地点调查员的威胁区，或地点上）。"""
        at_location: list[str] = []
        for other in ctx.game_state.get_investigators_at_location(inv.location_id):
            at_location.extend(other.threat_area)
        loc = ctx.game_state.get_location(inv.location_id)
        if loc is not None:
            at_location.extend(loc.enemies)

        def is_enemy(iid: str) -> bool:
            inst = ctx.game_state.get_card_instance(iid)
            data = ctx.game_state.get_card_data(inst.card_id) if inst else None
            return data is not None and data.type == CardType.ENEMY

        target_iid = ctx.extra.get("enemy_instance_id")
        if target_iid is not None:
            return target_iid if (target_iid in at_location
                                  and is_enemy(target_iid)) else None
        # 默认：优先自己威胁区，其次地点上的敌人
        for iid in inv.threat_area:
            if is_enemy(iid):
                return iid
        if loc is not None:
            for iid in loc.enemies:
                if is_enemy(iid):
                    return iid
        return None

    @on_event(GameEvent.ATTACK_OF_OPPORTUNITY, priority=TimingPriority.WHEN)
    def cancel_aoo(self, ctx):
        """打出本卡的行动不引起趁乱攻击。"""
        if self._aoo_free is not None and ctx.investigator_id == self._aoo_free:
            ctx.cancel()

    @on_event(GameEvent.ACTION_PERFORMED, priority=TimingPriority.AFTER)
    def clear_aoo(self, ctx):
        self._aoo_free = None
