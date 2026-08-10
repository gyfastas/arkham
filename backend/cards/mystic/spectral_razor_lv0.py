"""Spectral Razor (Level 0) — Mystic Event. (06201)
攻击。本次攻击将你的[willpower]值加入技能值。紧在本次攻击之前，你可以与
被攻击的敌人交战。本次攻击造成+1伤害（若该敌人非[[精英]]，改为+2伤害）。

简化说明：
- 打出后经 CARD_PLAYED 武装；由会话层发起战斗行动（同 storm_of_spirits
  惯例）。被攻击目标经 FIGHT_ACTION_INITIATED 记录。
- "可以与被攻击的敌人交战"简化为自动交战（未与你交战时才移动）。
- 非精英判定经 scenarios.official_core.is_elite_enemy（traits/keywords）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority
from backend.scenarios.official_core import is_elite_enemy


class SpectralRazor(CardImplementation):
    card_id = "spectral_razor_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._armed_by: str | None = None
        self._target_enemy_id: str | None = None

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def arm(self, ctx):
        if ctx.extra.get("card_id") != self.card_id:
            return
        if ctx.game_state.get_investigator(ctx.investigator_id) is None:
            return
        self._armed_by = ctx.investigator_id
        self._target_enemy_id = None

    @on_event(GameEvent.FIGHT_ACTION_INITIATED, priority=TimingPriority.WHEN)
    def engage_target(self, ctx):
        """记录被攻击敌人；紧在攻击前自动与其交战。"""
        if self._armed_by is None or ctx.investigator_id != self._armed_by:
            return
        self._target_enemy_id = ctx.enemy_id
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        enemy = ctx.game_state.get_card_instance(ctx.enemy_id)
        if inv is None or enemy is None or ctx.enemy_id in inv.threat_area:
            return
        for loc in ctx.game_state.locations.values():
            if ctx.enemy_id in loc.enemies:
                loc.enemies.remove(ctx.enemy_id)
        for other in ctx.game_state.investigators.values():
            if ctx.enemy_id in other.threat_area:
                other.threat_area.remove(ctx.enemy_id)
        inv.threat_area.append(ctx.enemy_id)
        bus = getattr(self, "_bus", None)
        if bus is not None:
            from backend.engine.event_bus import EventContext
            bus.emit(EventContext(
                game_state=ctx.game_state,
                event=GameEvent.ENEMY_ENGAGED,
                investigator_id=ctx.investigator_id,
                enemy_id=ctx.enemy_id,
            ))
        ctx.extra["spectral_razor_engaged"] = True

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def add_willpower(self, ctx):
        """本次攻击将意志值加入技能值（战斗基础值保留）。"""
        if self._armed_by is None or ctx.investigator_id != self._armed_by:
            return
        if ctx.skill_type != Skill.COMBAT:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        ctx.modify_amount(
            inv.get_skill(Skill.WILLPOWER), "spectral_razor_willpower")

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.WHEN)
    def bonus_damage(self, ctx):
        """+1伤害（非精英敌人 +2）。"""
        if self._armed_by is None or ctx.investigator_id != self._armed_by:
            return
        if ctx.skill_type != Skill.COMBAT:
            return
        bonus = 1
        enemy = ctx.game_state.get_card_instance(self._target_enemy_id) \
            if self._target_enemy_id else None
        cd = ctx.game_state.get_card_data(enemy.card_id) if enemy else None
        if cd is not None and not is_elite_enemy(cd):
            bonus = 2
        ctx.extra["bonus_damage"] = ctx.extra.get("bonus_damage", 0) + bonus
        ctx.extra["spectral_razor_bonus"] = bonus

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._armed_by = None
        self._target_enemy_id = None

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus
