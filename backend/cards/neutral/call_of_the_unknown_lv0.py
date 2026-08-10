"""Call of the Unknown (Level 0) — Neutral Treachery, Weakness.
显现：放置入你的威胁区域。
强制 - 你的回合开始时：选择1个你所在地点以外的地点。当你的回合结束时，
若你本回合没有成功调查所选地点，受到2点恐惧并将未知呼唤洗回你的牌组。

简化说明：
- "选择1个地点"自动选择第一个其他地点（官方为玩家选择）。
- "成功调查"以智力检定成功且检定时你位于所选地点近似（技能检定成功
  事件不含地点上下文，以调查员当前地点判定）。
- 成功调查过则本卡留在威胁区，下回合再次触发。
"""

import random

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class CallOfTheUnknown(CardImplementation):
    card_id = "call_of_the_unknown_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._chosen_location: str | None = None
        self._investigated = False

    @on_event(GameEvent.CARD_DRAWN, priority=TimingPriority.WHEN)
    def revelation(self, ctx):
        if ctx.extra.get("card_id") != "call_of_the_unknown_lv0":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if "call_of_the_unknown_lv0" in inv.hand:
            inv.hand.remove("call_of_the_unknown_lv0")

        from backend.models.state import CardInstance
        inst_id = ctx.game_state.next_instance_id()
        ci = CardInstance(
            instance_id=inst_id,
            card_id="call_of_the_unknown_lv0",
            owner_id=ctx.investigator_id,
            controller_id=ctx.investigator_id,
        )
        ctx.game_state.cards_in_play[inst_id] = ci
        inv.threat_area.append(inst_id)

    @on_event(GameEvent.INVESTIGATOR_TURN_BEGINS, priority=TimingPriority.FORCED)
    def choose_location(self, ctx):
        """回合开始时：选择1个其他地点（自动选第一个）。"""
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if self._find_call(ctx.game_state, inv) is None:
            return
        self._investigated = False
        self._chosen_location = None
        for loc_id in ctx.game_state.locations:
            if loc_id != inv.location_id:
                self._chosen_location = loc_id
                break
        if self._chosen_location:
            ctx.game_state.log_effect(
                f"🧭 未知呼唤：本回合需成功调查 {self._chosen_location}")

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.AFTER)
    def track_investigation(self, ctx):
        """在所选地点成功调查（智力检定成功）。"""
        if self._chosen_location is None:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if self._find_call(ctx.game_state, inv) is None:
            return
        if ctx.skill_type != Skill.INTELLECT:
            return
        if inv.location_id == self._chosen_location:
            self._investigated = True

    @on_event(GameEvent.INVESTIGATOR_TURN_ENDS, priority=TimingPriority.AFTER)
    def judge_at_turn_end(self, ctx):
        """回合结束时：未成功调查所选地点则受2点恐惧并洗回牌组。"""
        if self._chosen_location is None:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        inst = self._find_call(ctx.game_state, inv)
        if inst is None:
            return
        if self._investigated:
            ctx.extra["call_of_the_unknown_satisfied"] = True
            return
        inv.horror += 2  # 直接恐惧（不分配）
        inv.threat_area.remove(inst.instance_id)
        ctx.game_state.cards_in_play.pop(inst.instance_id, None)
        inv.deck.append("call_of_the_unknown_lv0")
        random.shuffle(inv.deck)
        ctx.extra["call_of_the_unknown_shuffled_back"] = True
        ctx.game_state.log_effect(
            "🧭 未知呼唤：未调查所选地点，受2点恐惧并洗回牌组")

    @staticmethod
    def _find_call(game_state, inv):
        for inst_id in inv.threat_area:
            inst = game_state.get_card_instance(inst_id)
            if inst is not None and inst.card_id == "call_of_the_unknown_lv0":
                return inst
        return None
