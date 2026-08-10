"""Drawing the Sign (Level 0) — Neutral Treachery, Basic Weakness.
显现：放置入你的威胁区域。
你的手牌上限降低5张（FAQ v1.6）。
[action][action]：丢弃涂绘印记。

实现说明：
- 手牌上限通过 UPKEEP_PHASE_BEGINS 的 limit ctx（phase_upkeep._check_hand_size
  以 ctx.amount 为上限）扣减 5 实现。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority
from backend.models.state import CardInstance


class DrawingTheSign(CardImplementation):
    card_id = "drawing_the_sign_lv0"
    activations = [{"id": "discard", "label": "[行动×2] 丢弃涂绘印记", "method": "activate_discard", "actions": 2}]

    @on_event(GameEvent.CARD_DRAWN, priority=TimingPriority.WHEN)
    def revelation(self, ctx):
        if ctx.extra.get("card_id") != "drawing_the_sign_lv0":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if "drawing_the_sign_lv0" in inv.hand:
            inv.hand.remove("drawing_the_sign_lv0")

        inst_id = ctx.game_state.next_instance_id()
        ci = CardInstance(
            instance_id=inst_id,
            card_id="drawing_the_sign_lv0",
            owner_id=ctx.investigator_id,
            controller_id=ctx.investigator_id,
        )
        ctx.game_state.cards_in_play[inst_id] = ci
        inv.threat_area.append(inst_id)

    @on_event(GameEvent.UPKEEP_PHASE_BEGINS, priority=TimingPriority.WHEN)
    def reduce_hand_size(self, ctx):
        """你的手牌上限降低5张。"""
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if self._find_in_threat(ctx.game_state, inv) is None:
            return
        ctx.modify_amount(-5, "drawing_the_sign_hand_size")

    def activate_discard(self, game_state, investigator_id) -> bool:
        """[action][action]：丢弃涂绘印记。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return False
        inst = self._find_in_threat(game_state, inv)
        if inst is None:
            return False
        inv.threat_area.remove(inst.instance_id)
        game_state.cards_in_play.pop(inst.instance_id, None)
        inv.discard.append("drawing_the_sign_lv0")
        return True

    @staticmethod
    def _find_in_threat(game_state, inv):
        for inst_id in inv.threat_area:
            inst = game_state.get_card_instance(inst_id)
            if inst is not None and inst.card_id == "drawing_the_sign_lv0":
                return inst
        return None
