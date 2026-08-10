"""Hoods (Level 0) — Neutral Enemy, Weakness (Rita Young).
猎物 - 仅限丽塔·杨。警觉。猎手。
强制 - 在你躲避暴徒后：它攻击你。

简化说明：
- 猎物/警觉/猎手关键词与生成通道由会话层/数据层负责（同
  graveyard_ghouls_lv0 说明；敌人数值不在玩家卡 JSON 加载通道内）。
- "它攻击你"：躲避成功后敌人已横置并脱离交战，官方规定其仍攻击；
  实现为发出 ENEMY_ATTACKS（可被 Dodge 等取消）后按敌人数据结算伤害/恐惧
  （经 DamageEngine，可正常分配给支援卡）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.engine.event_bus import EventContext
from backend.models.enums import GameEvent, TimingPriority


class Hoods(CardImplementation):
    card_id = "hoods_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._bus = None

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus

    @on_event(GameEvent.ENEMY_EVADED, priority=TimingPriority.AFTER)
    def attack_after_evade(self, ctx):
        enemy = ctx.game_state.get_card_instance(ctx.enemy_id)
        if enemy is None or enemy.card_id != "hoods_lv0":
            return
        enemy_data = ctx.game_state.get_card_data(enemy.card_id)
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if enemy_data is None or inv is None:
            return

        attack_ctx = EventContext(
            game_state=ctx.game_state,
            event=GameEvent.ENEMY_ATTACKS,
            investigator_id=ctx.investigator_id,
            enemy_id=ctx.enemy_id,
        )
        if self._bus is not None:
            self._bus.emit(attack_ctx)
        if attack_ctx.cancelled:
            ctx.game_state.log_effect("🥷 暴徒的反击攻击被取消")
            return

        from backend.engine.damage import DamageEngine
        DamageEngine(ctx.game_state, self._bus).deal_damage(
            ctx.investigator_id,
            damage=enemy_data.enemy_damage or 0,
            horror=enemy_data.enemy_horror or 0,
            source=ctx.enemy_id,
        )
        ctx.game_state.log_effect("🥷 暴徒：被躲避后立即攻击你")
