"""Breaking and Entering (Level 0) — Rogue Event. (07114)
调查。将你的敏捷值加入你这次调查的技能值。如果你成功且超过难度至少2点，
你可以自动躲避此地点的一名敌人。这个行动不会引起趁乱攻击。

简化说明：
- 打出后武装（active_effects，backstab/cheap_shot 同模式）；随后由会话层
  发起调查行动，检定时将敏捷值加入技能值。
- 成功超2的自动躲避：默认选此地点第一个敌人（优先你交战区），可经
  ctx.extra["bae_evade_target"] 指定（官方为玩家自选）；复刻引擎躲避成功
  结算并发出 ENEMY_EVADED（cheap_shot 同例）。
- "不引起趁乱攻击"：在随后的调查行动发起时挂起豁免标记，拦截紧随的一次
  趁乱攻击（lupara 打出窗口同模式）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority

_ARM_KEY = "breaking_and_entering_lv0"
_NO_AOO_KEY = "breaking_and_entering_no_aoo"


class BreakingAndEntering(CardImplementation):
    card_id = "breaking_and_entering_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._bus = None

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def arm(self, ctx):
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if not hasattr(inv, "active_effects"):
            inv.active_effects = {}
        inv.active_effects[_ARM_KEY] = True

    @on_event(GameEvent.INVESTIGATE_ACTION_INITIATED, priority=TimingPriority.WHEN)
    def arm_no_aoo(self, ctx):
        """随后的调查行动不引起趁乱攻击。"""
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if getattr(inv, "active_effects", {}).get(_ARM_KEY):
            inv.active_effects[_NO_AOO_KEY] = True

    @on_event(GameEvent.ATTACK_OF_OPPORTUNITY, priority=TimingPriority.WHEN)
    def cancel_aoo(self, ctx):
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        effects = getattr(inv, "active_effects", {})
        if not effects.get(_NO_AOO_KEY):
            return
        effects.pop(_NO_AOO_KEY, None)
        ctx.cancel()
        ctx.game_state.log_effect("🚪 破门而入：该调查不引起趁乱攻击")

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def add_agility(self, ctx):
        """本次调查：将敏捷值加入技能值。"""
        if ctx.skill_type != Skill.INTELLECT:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if not getattr(inv, "active_effects", {}).get(_ARM_KEY):
            return
        ctx.modify_amount(inv.get_skill(Skill.AGILITY), "breaking_and_entering_agility")

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.AFTER)
    def auto_evade(self, ctx):
        """成功且超出难度至少2点：自动躲避此地点的一名敌人。"""
        if ctx.skill_type != Skill.INTELLECT:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if not getattr(inv, "active_effects", {}).get(_ARM_KEY):
            return
        margin = (ctx.modified_skill or 0) - (ctx.difficulty or 0)
        if margin < 2:
            return

        # 目标：extra 指定，否则你交战区第一个，否则地点第一个未交战敌人
        target_id = ctx.extra.get("bae_evade_target")
        if target_id is None:
            if inv.threat_area:
                target_id = inv.threat_area[0]
            else:
                loc = ctx.game_state.get_location(inv.location_id)
                if loc is not None and loc.enemies:
                    target_id = loc.enemies[0]
        enemy = ctx.game_state.get_card_instance(target_id) if target_id else None
        if enemy is None:
            return

        # 复刻引擎躲避成功结算（actions._evade.on_success）
        enemy.exhausted = True
        for other in ctx.game_state.investigators.values():
            if target_id in other.threat_area:
                other.threat_area.remove(target_id)
        location = ctx.game_state.get_location(inv.location_id)
        if location is not None and target_id not in location.enemies:
            location.enemies.append(target_id)

        ctx.extra["breaking_and_entering_evaded"] = target_id
        ctx.game_state.log_effect("🚪 破门而入：成功超2，自动躲避一名敌人")
        if self._bus is not None:
            from backend.engine.event_bus import EventContext
            self._bus.emit(EventContext(
                game_state=ctx.game_state,
                event=GameEvent.ENEMY_EVADED,
                investigator_id=ctx.investigator_id,
                enemy_id=target_id,
            ))

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        for inv in ctx.game_state.investigators.values():
            effects = getattr(inv, "active_effects", None)
            if effects:
                effects.pop(_ARM_KEY, None)

    @on_event(GameEvent.ACTION_PERFORMED, priority=TimingPriority.AFTER)
    def clear_no_aoo(self, ctx):
        for inv in ctx.game_state.investigators.values():
            effects = getattr(inv, "active_effects", None)
            if effects:
                effects.pop(_NO_AOO_KEY, None)
