"""Sneak Attack (Level 0) — Rogue Event.
对你所在地点的一个已横置敌人造成2点伤害。

简化说明：
- 引擎的 CARD_PLAYED 不透传玩家选择的目标；默认选择你所在地点
  第一个已横置敌人（可用 ctx.extra["target_enemy_id"] 显式指定，
  指定时校验该敌人已横置且在你所在地点）。
"""
from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class SneakAttack(CardImplementation):
    card_id = "sneak_attack_lv0"

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def deal_damage(self, ctx):
        """Deal 2 damage to an exhausted enemy at your location."""
        if ctx.extra.get("card_id") != "sneak_attack_lv0":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        loc = ctx.game_state.get_location(inv.location_id)
        if loc is None:
            return

        target_id = ctx.extra.get("target_enemy_id")
        enemy = None
        if target_id:
            # 显式目标：校验已横置且在你所在地点
            enemy = ctx.game_state.get_card_instance(target_id)
            if enemy is None or not enemy.exhausted or target_id not in loc.enemies:
                return
        else:
            # 默认目标：你所在地点第一个已横置敌人
            for eid in loc.enemies:
                candidate = ctx.game_state.get_card_instance(eid)
                if candidate is not None and candidate.exhausted:
                    target_id = eid
                    enemy = candidate
                    break
            if enemy is None:
                return

        enemy.damage = getattr(enemy, "damage", 0) + 2
        ctx.extra["sneak_attack_target"] = target_id
