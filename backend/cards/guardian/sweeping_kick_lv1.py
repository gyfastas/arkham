"""Sweeping Kick (Level 1) — Guardian Event. (08023)
<b>攻击</b>。这次攻击将你的[agility]加入你的技能值。这次攻击造成+1伤害。
如果你成功，自动躲避被攻击的敌人。

简化说明：
- 打出后由会话层发起战斗行动；武装期间持有者的下一次战斗检定即本次攻击。
- 目标经 ctx.extra["enemy_instance_id"] 指定，缺省取威胁区第一个敌人。
- 自动躲避在攻击结算后（SKILL_TEST_ENDS，伤害已结算）执行：敌人横置、脱离
  交战并放回持有者所在地点，发出 ENEMY_EVADED；若伤害已击败敌人则不再躲避。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class SweepingKick(CardImplementation):
    card_id = "sweeping_kick_lv1"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._bus = None
        self._armed_for: str | None = None
        self._target: str | None = None
        self._succeeded = False

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
        self._armed_for = inv.investigator_id
        self._target = ctx.extra.get("enemy_instance_id") or next(iter(inv.threat_area), None)
        self._succeeded = False

    def _is_this_attack(self, ctx) -> bool:
        return (
            self._armed_for is not None
            and ctx.investigator_id == self._armed_for
            and ctx.skill_type == Skill.COMBAT
        )

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def add_agility(self, ctx):
        """本次攻击将敏捷加入技能值。"""
        if not self._is_this_attack(ctx):
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        agility = inv.get_skill(Skill.AGILITY)
        if agility:
            ctx.modify_amount(agility, "sweeping_kick_agility")

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.WHEN)
    def bonus_damage(self, ctx):
        """+1伤害（经 bonus_damage 通道汇入），并记录成功以供自动躲避。"""
        if not self._is_this_attack(ctx):
            return
        ctx.extra["bonus_damage"] = ctx.extra.get("bonus_damage", 0) + 1
        self._succeeded = True

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def auto_evade(self, ctx):
        """攻击成功且目标仍在场：自动躲避被攻击的敌人。"""
        if self._armed_for is None or ctx.investigator_id != self._armed_for:
            return
        inv = ctx.game_state.get_investigator(self._armed_for)
        target = (
            ctx.game_state.get_card_instance(self._target)
            if self._target else None
        )
        if self._succeeded and inv is not None and target is not None:
            target.exhausted = True
            if self._target in inv.threat_area:
                inv.threat_area.remove(self._target)
            loc = ctx.game_state.get_location(inv.location_id)
            if loc is not None and self._target not in loc.enemies:
                loc.enemies.append(self._target)
            if self._bus is not None:
                from backend.engine.event_bus import EventContext
                self._bus.emit(EventContext(
                    game_state=ctx.game_state,
                    event=GameEvent.ENEMY_EVADED,
                    investigator_id=inv.investigator_id,
                    enemy_id=self._target,
                ))
            ctx.game_state.log_effect(
                f"🦵 扫堂腿：【{ctx.game_state.card_name(target.card_id)}】被自动躲避")
        self._armed_for = None
        self._target = None
        self._succeeded = False
