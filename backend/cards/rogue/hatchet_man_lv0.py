"""Hatchet Man (Level 0) — Rogue Skill. (04155)
若本次技能检定在躲避尝试中成功，本回合内被躲避的敌人下一次受到伤害时，
额外承受1点伤害。

简化说明：
- 投入的技能卡实现仅在检定流程内临时激活（ST.8 注销），而加伤发生在检定
  之后：经 persistent_in_hand 在抽到后持续注册（引擎手牌监听通道），状态
  存于调查员 active_effects（手牌实例与投入临时实例写同一标记，幂等）。
- 敏捷检定成功后武装；ENEMY_EVADED 记录被躲避的敌人；该敌人本回合下一次
  DAMAGE_DEALT 时 +1 伤害并消耗；回合结束过期。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority

_ARMED = "hatchet_man_lv0_armed"
_ENEMY = "hatchet_man_lv0_enemy"


class HatchetMan(CardImplementation):
    card_id = "hatchet_man_lv0"
    persistent_in_hand = True  # 跨检定监听加伤窗口（效果在投入后留存）

    @staticmethod
    def _effects(inv) -> dict:
        if not hasattr(inv, "active_effects"):
            inv.active_effects = {}
        return inv.active_effects

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.WHEN)
    def arm_on_evade_success(self, ctx):
        if "hatchet_man_lv0" not in ctx.committed_cards:
            return
        if ctx.skill_type != Skill.AGILITY:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is not None:
            self._effects(inv)[_ARMED] = True

    @on_event(GameEvent.ENEMY_EVADED, priority=TimingPriority.AFTER)
    def mark_enemy(self, ctx):
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        effects = self._effects(inv)
        if not effects.pop(_ARMED, False):
            return
        effects[_ENEMY] = ctx.enemy_id

    @on_event(GameEvent.DAMAGE_DEALT, priority=TimingPriority.WHEN)
    def bonus_damage(self, ctx):
        """被躲避的敌人本回合下一次受到伤害时 +1 伤害（任何来源）。"""
        for inv in ctx.game_state.investigators.values():
            effects = getattr(inv, "active_effects", None) or {}
            enemy_id = effects.get(_ENEMY)
            if enemy_id is None or ctx.target != enemy_id:
                continue
            effects.pop(_ENEMY, None)
            ctx.modify_amount(1, "hatchet_man_bonus_damage")
            ctx.extra["hatchet_man_bonus"] = True
            ctx.game_state.log_effect("🪓 刽子手：被躲避的敌人额外承受1点伤害")
            return

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear_armed(self, ctx):
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is not None and hasattr(inv, "active_effects"):
            inv.active_effects.pop(_ARMED, None)

    @on_event(GameEvent.INVESTIGATOR_TURN_ENDS, priority=TimingPriority.AFTER)
    def expire(self, ctx):
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is not None and hasattr(inv, "active_effects"):
            inv.active_effects.pop(_ENEMY, None)
