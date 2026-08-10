"""Ice Pick (Level 1) — Seeker Asset, Hand slot. (08105)
快速。
[快速]攻击或调查时的技能检定中，消耗破冰锥：你这次检定+1技能值。

简化说明：
- use() 消耗本卡并武装（快速能力，由会话层/玩家在检定中调用）；
- "攻击或调查时"经 FIGHT/INVESTIGATE_ACTION_INITIATED 跟踪
  （与 magnifying_glass 同模式），武装在 SKILL_TEST_ENDS 清除；
- 加值对武装后的下一次攻击（战斗力）或调查（智力）检定生效一次。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class IcePick(CardImplementation):
    card_id = "ice_pick_lv1"
    activations = [{
        "id": "boost",
        "label": "[快速]攻击/调查检定中消耗：本次检定+1技能值",
        "method": "use",
    }]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._armed = False
        self._fighting: str | None = None
        self._investigating: str | None = None

    def use(self, game_state, investigator_id: str) -> bool:
        """消耗破冰锥：本次攻击/调查检定+1技能值。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None or inst.exhausted:
            return False
        inst.exhausted = True
        self._armed = True
        return True

    def _is_armed_fight(self, ctx) -> bool:
        return (self._armed and ctx.skill_type == Skill.COMBAT
                and self._fighting == ctx.investigator_id)

    def _is_armed_investigate(self, ctx) -> bool:
        return (self._armed and ctx.skill_type == Skill.INTELLECT
                and self._investigating == ctx.investigator_id)

    @on_event(GameEvent.FIGHT_ACTION_INITIATED, priority=TimingPriority.AFTER)
    def track_fight(self, ctx):
        self._fighting = ctx.investigator_id

    @on_event(GameEvent.INVESTIGATE_ACTION_INITIATED, priority=TimingPriority.AFTER)
    def track_investigate(self, ctx):
        self._investigating = ctx.investigator_id

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def skill_bonus(self, ctx):
        """武装后的攻击/调查检定：+1技能值。"""
        if not (self._is_armed_fight(ctx) or self._is_armed_investigate(ctx)):
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv and self.instance_id in inv.play_area:
            ctx.modify_amount(1, "ice_pick_bonus")

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._armed = False
        self._fighting = None
        self._investigating = None
