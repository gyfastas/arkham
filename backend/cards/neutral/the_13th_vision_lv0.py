"""The 13th Vision (Level 0) — Neutral Treachery, Basic Weakness. (05041)
显现 - 将第13幻象放置入你的威胁区域。
你所在地点的调查员在技能检定的平局时视为失败。
[action][action]：丢弃第13幻象。

简化说明：
- "平局失败"依赖 skill_test 引擎对 ctx.success 的回读（同 rexs_curse_lv0）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class The13thVision(CardImplementation):
    card_id = "the_13th_vision_lv0"
    activations = [{"id": "discard", "label": "[行动×2] 丢弃第13幻象", "method": "activate_discard", "actions": 2}]

    @on_event(GameEvent.CARD_DRAWN, priority=TimingPriority.WHEN)
    def revelation(self, ctx):
        if ctx.extra.get("card_id") != "the_13th_vision_lv0":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if "the_13th_vision_lv0" in inv.hand:
            inv.hand.remove("the_13th_vision_lv0")

        from backend.models.state import CardInstance
        inst_id = ctx.game_state.next_instance_id()
        ci = CardInstance(
            instance_id=inst_id,
            card_id="the_13th_vision_lv0",
            owner_id=ctx.investigator_id,
            controller_id=ctx.investigator_id,
        )
        ctx.game_state.cards_in_play[inst_id] = ci
        inv.threat_area.append(inst_id)

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.WHEN)
    def fail_ties(self, ctx):
        """你所在地点的调查员检定平局（技能值==难度）时失败。"""
        owner = self._owner(ctx.game_state)
        if owner is None:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or inv.location_id != owner.location_id:
            return
        if ctx.modified_skill is None or ctx.difficulty is None:
            return
        if ctx.modified_skill == ctx.difficulty:
            ctx.success = False
            ctx.extra["the_13th_vision_tie_failed"] = True

    def activate_discard(self, game_state, investigator_id) -> bool:
        """[action][action]：丢弃第13幻象。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return False
        inst = self._find(game_state, inv)
        if inst is None:
            return False
        inv.threat_area.remove(inst.instance_id)
        game_state.cards_in_play.pop(inst.instance_id, None)
        inv.discard.append("the_13th_vision_lv0")
        return True

    def _owner(self, game_state):
        for inv in game_state.investigators.values():
            if self._find(game_state, inv) is not None:
                return inv
        return None

    @staticmethod
    def _find(game_state, inv):
        for inst_id in inv.threat_area:
            inst = game_state.get_card_instance(inst_id)
            if inst is not None and inst.card_id == "the_13th_vision_lv0":
                return inst
        return None
