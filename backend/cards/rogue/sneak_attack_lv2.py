"""Sneak Attack (Level 2) — Rogue Event.
对你所在地点的一个未与你交战的敌人造成2点伤害。

简化说明：
- 引擎的 CARD_PLAYED 不透传玩家选择的目标；默认选择你所在地点第一个
  未与你交战的敌人（地点上的未交战敌人优先，其次同地点与其他调查员
  交战的敌人），可用 ctx.extra["target_enemy_id"] 显式指定
  （指定时校验该敌人未与你交战且在你所在地点）。
- 伤害足够时按引擎流程击败敌人（ENEMY_DEFEATED 带 investigator_id
  与 extra.card_id；胜利点数入胜利牌堆）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import CardType, GameEvent, TimingPriority


class SneakAttackLv2(CardImplementation):
    card_id = "sneak_attack_lv2"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._bus = None

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus  # 击败敌人需要经事件总线发出 ENEMY_DEFEATED

    def _candidates(self, ctx, inv) -> list[str]:
        """你所在地点未与你交战的敌人实例 id 列表。"""
        loc = ctx.game_state.get_location(inv.location_id)
        if loc is None:
            return []
        candidates = [eid for eid in loc.enemies if eid not in inv.threat_area]
        for other in ctx.game_state.get_investigators_at_location(inv.location_id):
            if other.investigator_id == inv.investigator_id:
                continue
            candidates.extend(other.threat_area)
        return [
            eid for eid in candidates
            if (inst := ctx.game_state.get_card_instance(eid)) is not None
            and (ed := ctx.game_state.get_card_data(inst.card_id)) is not None
            and ed.type == CardType.ENEMY
        ]

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def deal_damage(self, ctx):
        """Deal 2 damage to an enemy not engaged with you at your location."""
        if ctx.extra.get("card_id") != "sneak_attack_lv2":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return

        valid = self._candidates(ctx, inv)
        target_id = ctx.extra.get("target_enemy_id")
        if target_id is not None:
            if target_id not in valid:
                return
        else:
            if not valid:
                return
            target_id = valid[0]

        enemy = ctx.game_state.get_card_instance(target_id)
        enemy_data = ctx.game_state.get_card_data(enemy.card_id)
        enemy.damage = getattr(enemy, "damage", 0) + 2
        ctx.extra["sneak_attack_lv2_target"] = target_id
        ctx.game_state.log_effect(
            f"🗡️ 偷袭：对{ctx.game_state.card_name(enemy.card_id)}造成2点伤害")

        # 伤害足够：按引擎流程击败敌人
        if enemy_data.enemy_health and enemy.damage >= enemy_data.enemy_health:
            self._defeat_enemy(ctx, target_id, enemy)

    def _defeat_enemy(self, ctx, instance_id: str, enemy) -> None:
        """复刻 DamageEngine._defeat_enemy 的结算。"""
        if self._bus is not None:
            from backend.engine.event_bus import EventContext
            self._bus.emit(EventContext(
                game_state=ctx.game_state,
                event=GameEvent.ENEMY_DEFEATED,
                target=instance_id,
                investigator_id=ctx.investigator_id,
                extra={"card_id": enemy.card_id},
            ))
        enemy_data = ctx.game_state.get_card_data(enemy.card_id)
        if enemy_data is not None and getattr(enemy_data, "victory", 0):
            ctx.game_state.scenario.victory_display.append(enemy.card_id)
        ctx.game_state.cards_in_play.pop(instance_id, None)
        for inv in ctx.game_state.investigators.values():
            if instance_id in inv.threat_area:
                inv.threat_area.remove(instance_id)
        for loc in ctx.game_state.locations.values():
            if instance_id in loc.enemies:
                loc.enemies.remove(instance_id)
        ctx.game_state.scenario.encounter_discard.append(enemy.card_id)
        ctx.extra["sneak_attack_lv2_defeated"] = instance_id
