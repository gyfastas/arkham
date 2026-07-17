"""Internal Injury — Neutral Treachery, Basic Weakness.
显现：放置入你的威胁区域。
强制 - 当你的回合结束时：受到1点直接伤害。
[action][action]：丢弃内伤。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class InternalInjury(CardImplementation):
    card_id = "internal_injury_lv0"

    @on_event(GameEvent.CARD_DRAWN, priority=TimingPriority.WHEN)
    def revelation(self, ctx):
        if ctx.extra.get("card_id") != "internal_injury_lv0":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if "internal_injury_lv0" in inv.hand:
            inv.hand.remove("internal_injury_lv0")

        from backend.models.state import CardInstance
        inst_id = ctx.game_state.next_instance_id()
        ci = CardInstance(
            instance_id=inst_id,
            card_id="internal_injury_lv0",
            owner_id=ctx.investigator_id,
            controller_id=ctx.investigator_id,
        )
        ctx.game_state.cards_in_play[inst_id] = ci
        inv.threat_area.append(inst_id)

    @on_event(GameEvent.INVESTIGATOR_TURN_ENDS, priority=TimingPriority.AFTER)
    def turn_end_damage(self, ctx):
        """你的回合结束时：受到1点直接伤害。"""
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if self._find_injury(ctx.game_state, inv) is None:
            return
        inv.damage += 1  # 直接伤害（不分配）

    def activate_discard(self, game_state, investigator_id) -> bool:
        """[action][action]：丢弃内伤。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return False
        inst = self._find_injury(game_state, inv)
        if inst is None:
            return False
        inv.threat_area.remove(inst.instance_id)
        game_state.cards_in_play.pop(inst.instance_id, None)
        inv.discard.append("internal_injury_lv0")
        return True

    @staticmethod
    def _find_injury(game_state, inv):
        for inst_id in inv.threat_area:
            inst = game_state.get_card_instance(inst_id)
            if inst is not None and inst.card_id == "internal_injury_lv0":
                return inst
        return None
