"""Cheap Shot (Level 0) — Rogue Event.
攻击。本次攻击中将你的敏捷值加入你的技能值。
若你成功且超出难度2点以上，自动躲避被攻击的敌人。

简化说明：
- 打出后由会话层发起战斗行动；本实现通过 active_effects 武装（backstab 同模式），
  在下一次战斗检定中将敏捷值加入技能值。
- 攻击目标在 FIGHT_ACTION_INITIATED 时锁定（SKILL_TEST 事件不带 enemy_id）。
- "自动躲避"复刻引擎躲避成功的结算：敌人横置、解除交战、放回地点，
  并经事件总线发出 ENEMY_EVADED（官方视为躲避，可触发扒窃等反应）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority

_ARM_KEY = "cheap_shot_lv0"
_TARGET_KEY = "cheap_shot_lv0_target"


class CheapShot(CardImplementation):
    card_id = "cheap_shot_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._bus = None

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus  # 自动躲避需要经事件总线发出 ENEMY_EVADED

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def arm(self, ctx):
        if ctx.extra.get("card_id") != "cheap_shot_lv0":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if not hasattr(inv, "active_effects"):
            inv.active_effects = {}
        inv.active_effects[_ARM_KEY] = True

    @on_event(GameEvent.FIGHT_ACTION_INITIATED, priority=TimingPriority.WHEN)
    def lock_target(self, ctx):
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if not getattr(inv, "active_effects", {}).get(_ARM_KEY):
            return
        inv.active_effects[_TARGET_KEY] = ctx.enemy_id

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def add_agility(self, ctx):
        """本次攻击：将敏捷值加入技能值。"""
        if ctx.skill_type != Skill.COMBAT:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if not getattr(inv, "active_effects", {}).get(_ARM_KEY):
            return
        ctx.modify_amount(inv.get_skill(Skill.AGILITY), "cheap_shot_agility")

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.AFTER)
    def auto_evade(self, ctx):
        """成功且超出难度2点以上：自动躲避被攻击的敌人。"""
        if ctx.skill_type != Skill.COMBAT:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        effects = getattr(inv, "active_effects", {})
        if not effects.get(_ARM_KEY):
            return
        margin = (ctx.modified_skill or 0) - (ctx.difficulty or 0)
        if margin < 2:
            return
        enemy_id = effects.get(_TARGET_KEY)
        enemy = ctx.game_state.get_card_instance(enemy_id) if enemy_id else None
        if enemy is None:
            return

        # 复刻引擎躲避成功结算（actions._evade.on_success）
        enemy.exhausted = True
        if enemy_id in inv.threat_area:
            inv.threat_area.remove(enemy_id)
        location = ctx.game_state.get_location(inv.location_id)
        if location is not None and enemy_id not in location.enemies:
            location.enemies.append(enemy_id)

        ctx.extra["cheap_shot_auto_evade"] = enemy_id
        ctx.game_state.log_effect("🥊 下流一击：成功超2，自动躲避被攻击的敌人")
        if self._bus is not None:
            from backend.engine.event_bus import EventContext
            self._bus.emit(EventContext(
                game_state=ctx.game_state,
                event=GameEvent.ENEMY_EVADED,
                investigator_id=ctx.investigator_id,
                enemy_id=enemy_id,
            ))

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        for inv in ctx.game_state.investigators.values():
            effects = getattr(inv, "active_effects", None)
            if effects:
                effects.pop(_ARM_KEY, None)
                effects.pop(_TARGET_KEY, None)
