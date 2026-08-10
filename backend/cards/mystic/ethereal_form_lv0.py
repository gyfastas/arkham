"""Ethereal Form (Level 0) — Mystic Event. (06164)
躲避。将你的[willpower]值加入你这次躲避尝试的技能值。如果你成功，与每名
与你交战的其余敌人解除交战，并且本轮接下来的时间里，你视为无形（敌人不能
与你交战，且你不能攻击或对敌人造成伤害）。

简化说明：
- 打出后由会话层发起躲避行动；本实现通过 active_effects 武装，
  在下一次敏捷（躲避）检定中把意志值加入技能值。
- 成功：其余与你交战的敌人解除交战（移回你所在地点，保持当前横置状态）。
- 无形状态记录在 inv.active_effects["ethereal_form_ethereal"]，本轮结束清除；
  期间拦截你的 FIGHT_ACTION_INITIATED 予以取消（"不能攻击"）；
  "敌人不能与你交战"无引擎拦截点（ENEMY_ENGAGED 无取消通道——引擎缺口），
  会话层/AI 应读取该标记。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority

ETHEREAL_FLAG = "ethereal_form_ethereal"


class EtherealForm(CardImplementation):
    card_id = "ethereal_form_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._armed_by: str | None = None

    def _is_armed(self, game_state, investigator_id) -> bool:
        if self._armed_by != investigator_id:
            return False
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return False
        return bool(getattr(inv, "active_effects", {}).get(self.card_id))

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def arm(self, ctx):
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if not hasattr(inv, "active_effects"):
            inv.active_effects = {}
        inv.active_effects[self.card_id] = True
        self._armed_by = ctx.investigator_id

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def add_willpower(self, ctx):
        """躲避检定：将意志值加入技能值（在敏捷基础上叠加）。"""
        if ctx.skill_type != Skill.AGILITY:
            return
        if not self._is_armed(ctx.game_state, ctx.investigator_id):
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        willpower = inv.get_skill(Skill.WILLPOWER)
        ctx.modify_amount(willpower, "ethereal_form_add_willpower")

    @on_event(GameEvent.ENEMY_EVADED, priority=TimingPriority.AFTER)
    def disengage_and_ethereal(self, ctx):
        """成功：解除其余交战，本轮视为无形。"""
        if not self._is_armed(ctx.game_state, ctx.investigator_id):
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        loc = ctx.game_state.get_location(inv.location_id)
        others = [eid for eid in inv.threat_area if eid != ctx.enemy_id]
        for eid in others:
            inv.threat_area.remove(eid)
            if loc is not None and eid not in loc.enemies:
                loc.enemies.append(eid)
        if others:
            ctx.extra["ethereal_form_disengaged"] = others
        inv.active_effects[ETHEREAL_FLAG] = True
        ctx.extra["ethereal_form_ethereal"] = True
        ctx.game_state.log_effect("👻 飘渺灵体：你本轮视为无形")

    @on_event(GameEvent.FIGHT_ACTION_INITIATED, priority=TimingPriority.WHEN)
    def block_fight(self, ctx):
        """无形期间不能攻击：取消你的战斗行动。"""
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if getattr(inv, "active_effects", {}).get(ETHEREAL_FLAG):
            ctx.cancel()
            ctx.game_state.log_effect("👻 飘渺灵体：无形状态下不能攻击")

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear_armed(self, ctx):
        for inv in ctx.game_state.investigators.values():
            getattr(inv, "active_effects", {}).pop(self.card_id, None)
        self._armed_by = None

    @on_event(GameEvent.ROUND_ENDS, priority=TimingPriority.AFTER)
    def clear_ethereal(self, ctx):
        for inv in ctx.game_state.investigators.values():
            getattr(inv, "active_effects", {}).pop(ETHEREAL_FLAG, None)
