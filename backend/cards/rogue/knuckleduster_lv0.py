"""Knuckleduster (Level 0) — Rogue Asset, Hand slot.
[行动]：攻击。这次攻击造成+1伤害。这次攻击中被攻击的敌人获得反击。

简化说明：
- 武器攻击走标准武器流程（ctx.source 为本武器实例）。
- +1伤害在 SKILL_TEST_SUCCESSFUL 写入 ctx.extra["bonus_damage"]，由引擎结算。
- "获得反击"在 SKILL_TEST_FAILED 直接结算：被攻击敌人对你造成等同于
  其攻击力的伤害/恐惧（引擎的反击只认关键词，无法临时注入；
  若敌人本身已有反击关键词则跳过，避免双重结算——官方反击不叠加）。
- 攻击目标在 FIGHT_ACTION_INITIATED 时锁定（SKILL_TEST 事件不带 enemy_id）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class Knuckleduster(CardImplementation):
    card_id = "knuckleduster_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._target_enemy_id: str | None = None

    @on_event(GameEvent.FIGHT_ACTION_INITIATED, priority=TimingPriority.WHEN)
    def lock_target(self, ctx):
        if ctx.source != self.instance_id:
            return
        self._target_enemy_id = ctx.enemy_id

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.AFTER)
    def bonus_damage(self, ctx):
        """本次攻击造成+1伤害。"""
        if ctx.source != self.instance_id:
            return
        if ctx.skill_type != Skill.COMBAT:
            return
        ctx.extra["bonus_damage"] = int(ctx.extra.get("bonus_damage", 0) or 0) + 1

    @on_event(GameEvent.SKILL_TEST_FAILED, priority=TimingPriority.AFTER)
    def grant_retaliate(self, ctx):
        """攻击失败：被攻击的敌人获得反击，对你结算一次攻击。"""
        if ctx.source != self.instance_id:
            return
        if ctx.skill_type != Skill.COMBAT:
            return
        enemy_id = self._target_enemy_id
        enemy = ctx.game_state.get_card_instance(enemy_id) if enemy_id else None
        if enemy is None:
            return
        enemy_data = ctx.game_state.get_card_data(enemy.card_id)
        if enemy_data is None:
            return
        if "retaliate" in (enemy_data.keywords or []):
            return  # 已有反击：引擎会结算，不叠加
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        inv.damage += enemy_data.enemy_damage or 0
        inv.horror += enemy_data.enemy_horror or 0
        ctx.extra["knuckleduster_retaliate"] = enemy_id
        ctx.game_state.log_effect("🥊 指虎：攻击失败，敌人反击命中")

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        if ctx.source == self.instance_id:
            self._target_enemy_id = None
