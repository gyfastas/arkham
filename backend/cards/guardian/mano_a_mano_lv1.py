"""Mano a Mano (Level 1) — Guardian Event. (03229)
只可作为你的第一个行动打出。对与你交战的一个敌人造成1点伤害。
此行动不会引起趁乱攻击。

简化说明：
- "第一个行动"：引擎只跟踪 actions_remaining（回合开始重置为3），本卡以
  actions_remaining >= 3 近似判定（携带额外行动资产时不精确；完整校验由
  会话层负责，此处仅作防御）。不满足时效果不结算（注明）。
- 目标自动选择威胁区第一个敌人；会话层可经 ctx.extra["enemy_instance_id"]
  指定其他与你交战的敌人。
- 伤害经 _shared.deal_damage_to_enemy 结算（含击败流程，发出 ENEMY_DEFEATED）。
- 不引起趁乱攻击：CARD_PLAYED 先于 AoO 发出，武装一次性豁免标记。
"""

from backend.cards._shared import deal_damage_to_enemy
from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class ManoAMano(CardImplementation):
    card_id = "mano_a_mano_lv1"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._bus = None
        self._aoo_free = None

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def punch(self, ctx):
        """第一个行动：对与你交战的一个敌人造成1点伤害。"""
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if inv.actions_remaining < 3:
            # 简化：满行动视作本回合第一个行动（见 docstring）
            ctx.extra["mano_a_mano_fizzle"] = True
            ctx.game_state.log_effect("👊 单挑：不是本回合第一个行动，效果不结算")
            return

        target_iid = ctx.extra.get("enemy_instance_id")
        if target_iid is None or target_iid not in inv.threat_area:
            target_iid = next(iter(inv.threat_area), None)
        if target_iid is None:
            ctx.extra["mano_a_mano_fizzle"] = True
            return

        deal_damage_to_enemy(ctx.game_state, self._bus, target_iid, 1,
                             defeated_by=inv.investigator_id)
        ctx.extra["mano_a_mano_target"] = target_iid
        ctx.game_state.log_effect("👊 单挑：对交战的敌人造成1点伤害")

        # 此行动不引起趁乱攻击
        self._aoo_free = inv.investigator_id

    @on_event(GameEvent.ATTACK_OF_OPPORTUNITY, priority=TimingPriority.WHEN)
    def cancel_aoo(self, ctx):
        """打出本卡的行动不引起趁乱攻击。"""
        if self._aoo_free is not None and ctx.investigator_id == self._aoo_free:
            ctx.cancel()

    @on_event(GameEvent.ACTION_PERFORMED, priority=TimingPriority.AFTER)
    def clear_aoo(self, ctx):
        self._aoo_free = None
