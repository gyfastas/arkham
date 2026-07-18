"""Survival Instinct (Level 0) — Survivor Skill.
快速。在你躲避检定失败时打出。改为成功，然后你可以移动到一个连接地点。

简化说明：
- 投入该技能的躲避检定失败时：翻转结果（依赖 engine 对 ctx.success 的回读），
  并自动移动到第一个连接地点。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class SurvivalInstinct(CardImplementation):
    card_id = "survival_instinct_lv0"

    @on_event(GameEvent.SKILL_TEST_FAILED, priority=TimingPriority.WHEN)
    def turn_evade_to_success(self, ctx):
        if "survival_instinct_lv0" not in ctx.committed_cards:
            return
        if ctx.skill_type != Skill.AGILITY:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return

        ctx.success = True
        ctx.extra["survival_instinct_turned"] = True

        # 然后移动到一个连接地点
        loc = ctx.game_state.get_location(inv.location_id)
        if loc is not None:
            connections = getattr(loc, "connections", []) or []
            if connections and connections[0] in ctx.game_state.locations:
                inv.location_id = connections[0]
                ctx.extra["survival_instinct_moved_to"] = connections[0]
