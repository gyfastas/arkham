""""I'll see you in hell!" (Level 0) — Guardian Event. (03189)
击败与你交战的每个非精英敌人。你被击败并承受1点肉体创伤。
本行动不会引起趁乱攻击。

简化说明：
- 敌人击败经 _shared.defeat_enemy 结算（发出 ENEMY_DEFEATED、处理胜利牌堆、
  离场入遭遇弃牌堆），与引擎 DamageEngine 流程一致。
- "你被击败"实现为将已受伤害设为生命上限（is_defeated 成立）并发出
  INVESTIGATOR_DEFEATED；1点肉体创伤记录在 investigator_card
  （无 investigator_card 时记录在状态对象上，与 smite_the_wicked 一致）。
- 不引起趁乱攻击：CARD_PLAYED 在行动结算链中先于 AoO 发出，此处武装
  一次性豁免标记，取消随后的 ATTACK_OF_OPPORTUNITY，行动完成时清除。
"""

from backend.cards._shared import defeat_enemy
from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class IllSeeYouInHell(CardImplementation):
    card_id = "ill_see_you_in_hell_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._bus = None
        self._aoo_free = None  # 获得 AoO 豁免的调查员 id

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def go_out_in_a_blaze(self, ctx):
        """击败所有与你交战的非精英敌人，然后你被击败并承受1肉体创伤。"""
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return

        defeated = []
        for enemy_iid in list(inv.threat_area):
            enemy = ctx.game_state.get_card_instance(enemy_iid)
            enemy_data = ctx.game_state.get_card_data(enemy.card_id) if enemy else None
            if enemy_data is None or "elite" in (enemy_data.keywords or []):
                continue
            defeat_enemy(ctx.game_state, self._bus, enemy_iid,
                         defeated_by=inv.investigator_id)
            defeated.append(enemy_iid)
        ctx.extra["ill_see_you_in_hell_defeated"] = defeated
        if defeated:
            ctx.game_state.log_effect(f"💥 地狱见！：同归于尽，击败{len(defeated)}个敌人")

        # 你被击败并承受1点肉体创伤
        inv.damage = inv.health
        inv_card = inv.investigator_card
        if inv_card is not None:
            inv_card.physical_trauma = getattr(inv_card, "physical_trauma", 0) + 1
        else:
            inv.physical_trauma = getattr(inv, "physical_trauma", 0) + 1
        ctx.game_state.log_effect("💥 地狱见！：你被击败，承受1点肉体创伤")
        if self._bus is not None:
            from backend.engine.event_bus import EventContext
            self._bus.emit(EventContext(
                game_state=ctx.game_state,
                event=GameEvent.INVESTIGATOR_DEFEATED,
                investigator_id=inv.investigator_id,
            ))

        # 本行动不引起趁乱攻击
        self._aoo_free = inv.investigator_id

    @on_event(GameEvent.ATTACK_OF_OPPORTUNITY, priority=TimingPriority.WHEN)
    def cancel_aoo(self, ctx):
        """打出本卡的行动不引起趁乱攻击。"""
        if self._aoo_free is not None and ctx.investigator_id == self._aoo_free:
            ctx.cancel()

    @on_event(GameEvent.ACTION_PERFORMED, priority=TimingPriority.AFTER)
    def clear_aoo(self, ctx):
        self._aoo_free = None
