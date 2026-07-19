"""Dr. Milan Christopher (Level 0) — Seeker Asset, Ally slot.
你获得+1智力。
反应 - 在你成功调查后：获得1资源。

说明：
- "+1智力"对所有智力检定生效（与官方一致）。
- "成功调查后"必须是调查行动（investigate action）引发的智力检定，
  通过 INVESTIGATE_ACTION_INITIATED 跟踪（SKILL_TEST_ENDS 清除），
  避免普通智力检定（如诡计卡检定）误发资源。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class DrMilanChristopher(CardImplementation):
    card_id = "dr_milan_christopher_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._investigating: str | None = None

    @on_event(GameEvent.INVESTIGATE_ACTION_INITIATED, priority=TimingPriority.AFTER)
    def track_investigate(self, ctx):
        self._investigating = ctx.investigator_id

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear_tracking(self, ctx):
        self._investigating = None

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def intellect_bonus(self, ctx):
        """+1 Intellect while Dr. Milan is in play."""
        if ctx.skill_type != Skill.INTELLECT:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv and self.instance_id in inv.play_area:
            ctx.modify_amount(1, "dr_milan_intellect_bonus")

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.REACTION)
    def gain_resource_on_investigate(self, ctx):
        """成功调查后：消耗米兰博士，获得1资源（Taboo errata：需消耗，等效每轮限1次）。"""
        if ctx.skill_type != Skill.INTELLECT:
            return
        if self._investigating != ctx.investigator_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if self.instance_id not in inv.play_area:
            return
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None or inst.exhausted:
            return  # 已消耗（每轮限1次）
        inst.exhausted = True
        inv.resources += 1
        ctx.extra["dr_milan_resource"] = True
        ctx.game_state.log_effect("💰 米兰博士：成功调查，消耗米兰获得1资源")
