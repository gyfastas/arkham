"""Fortuitous Discovery (Level 0) — Survivor Event. Myriad.
X为你弃牌堆中其余意外的发现的数量。
调查。本次调查+X[智力]。若成功，在你所在地点额外发现X个线索。

简化说明：
- 打出时统计弃牌堆中其他意外的发现数量X，经 active_effects 武装，
  由会话层发起调查行动（同 backstab/act_of_desperation 模式）：
  智力检定+X，成功后所在地点额外发现至多X个线索（不足时按实际数量）。
- 多重（Myriad）为牌组构筑规则，无运行时效果。
- 不区分调查行动与其他智力检定（引擎的智力检定不携带行动来源，
  同 survival_instinct 的既有简化）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class FortuitousDiscovery(CardImplementation):
    card_id = "fortuitous_discovery_lv0"

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def arm(self, ctx):
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        x_value = sum(1 for cid in inv.discard if cid == self.card_id)
        if not hasattr(inv, "active_effects"):
            inv.active_effects = {}
        inv.active_effects[self.card_id] = {"x": x_value}
        ctx.extra["fortuitous_discovery_x"] = x_value
        if x_value:
            ctx.game_state.log_effect(
                f"🔍 意外的发现：弃牌堆中另有{x_value}张，本次调查+{x_value}智力")

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def intellect_bonus(self, ctx):
        if ctx.skill_type != Skill.INTELLECT:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        armed = getattr(inv, "active_effects", {}).get(self.card_id)
        if not armed:
            return
        ctx.modify_amount(armed["x"], "fortuitous_discovery_intellect")

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.AFTER)
    def discover_additional_clues(self, ctx):
        if ctx.skill_type != Skill.INTELLECT:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        armed = getattr(inv, "active_effects", {}).get(self.card_id)
        if not armed or armed["x"] < 1:
            return
        loc = ctx.game_state.get_location(inv.location_id)
        if loc is None:
            return
        found = min(armed["x"], loc.clues)
        if found > 0:
            loc.clues -= found
            inv.clues += found
            ctx.extra["fortuitous_discovery_clues"] = found
            ctx.game_state.log_effect(
                f"🔍 意外的发现：额外发现{found}个线索")

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        for inv in ctx.game_state.investigators.values():
            if hasattr(inv, "active_effects"):
                inv.active_effects.pop(self.card_id, None)
