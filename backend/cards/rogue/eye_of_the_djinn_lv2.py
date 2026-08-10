"""Eye of the Djinn (Level 2) — Rogue Asset. (07225)
卓绝。
[反应]当你在你的回合中发起技能检定时，消耗神灯之眼：本次检定你的基础
技能值视为5。若本次检定中揭示了[bless]标记，准备神灯之眼。若本次检定中
揭示了[curse]标记，你本回合可以执行1个额外行动。

简化说明：
- 反应窗口由 activate() 武装（UI/会话层在发起检定前调用），仅在你的回合
  可用（经 INVESTIGATOR_TURN_BEGINS/ENDS 跟踪）。
- [curse]的"可以执行1个额外行动"为可选；简化为自动+1行动（严格有利）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import ChaosTokenType, GameEvent, TimingPriority


class EyeOfTheDjinn(CardImplementation):
    card_id = "eye_of_the_djinn_lv2"
    activations = [{
        "id": "attune",
        "label": "消耗：本次检定基础技能值视为5",
        "method": "activate",
        "actions": 0,
    }]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._armed = False
        self._my_turn = False

    @on_event(GameEvent.INVESTIGATOR_TURN_BEGINS, priority=TimingPriority.AFTER)
    def track_turn_start(self, ctx):
        inst = ctx.game_state.get_card_instance(self.instance_id)
        self._my_turn = inst is not None and inst.owner_id == ctx.investigator_id

    @on_event(GameEvent.INVESTIGATOR_TURN_ENDS, priority=TimingPriority.AFTER)
    def track_turn_end(self, ctx):
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is not None and inst.owner_id == ctx.investigator_id:
            self._my_turn = False

    def activate(self, game_state, investigator_id: str) -> bool:
        """消耗：本次技能检定基础技能值视为5（仅你的回合）。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        if not self._my_turn:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None or inst.exhausted:
            return False
        inst.exhausted = True
        self._armed = True
        return True

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.WHEN)
    def bless_curse_reaction(self, ctx):
        """本次检定揭示[bless]：准备本卡；揭示[curse]：本回合+1行动。"""
        if not self._armed:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inv is None or inst is None or self.instance_id not in inv.play_area:
            return
        if ctx.chaos_token == ChaosTokenType.BLESS:
            inst.exhausted = False
            ctx.extra["eye_of_the_djinn_readied"] = True
            ctx.game_state.log_effect("👁 神灯之眼：揭示[bless]，准备神灯之眼")
        elif ctx.chaos_token == ChaosTokenType.CURSE:
            inv.actions_remaining += 1
            ctx.extra["eye_of_the_djinn_extra_action"] = True
            ctx.game_state.log_effect("👁 神灯之眼：揭示[curse]，本回合+1行动")

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def set_base_five(self, ctx):
        """本次检定基础技能值视为5（保留图标/标记/其他加值）。"""
        if not self._armed:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        base = ctx.extra.get("base_skill")
        if base is None:
            return
        ctx.modify_amount(5 - base, "eye_of_the_djinn_base_5")

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._armed = False
