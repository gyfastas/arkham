"""Hypochondria — Neutral Treachery, Basic Weakness.
显现：放到你的威胁区域。
强制 - 在你受到至少1点伤害后：受到1点直接恐惧。
[action][action]：丢弃忧郁症。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class Hypochondria(CardImplementation):
    card_id = "hypochondria"

    @on_event(GameEvent.CARD_DRAWN, priority=TimingPriority.WHEN)
    def revelation(self, ctx):
        if ctx.extra.get("card_id") != "hypochondria":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if "hypochondria" in inv.hand:
            inv.hand.remove("hypochondria")

        from backend.models.state import CardInstance
        inst_id = ctx.game_state.next_instance_id()
        ci = CardInstance(
            instance_id=inst_id,
            card_id="hypochondria",
            owner_id=ctx.investigator_id,
            controller_id=ctx.investigator_id,
        )
        ctx.game_state.cards_in_play[inst_id] = ci
        inv.threat_area.append(inst_id)

    @on_event(GameEvent.DAMAGE_DEALT, priority=TimingPriority.AFTER)
    def horror_after_damage(self, ctx):
        """你受到至少1点伤害后：受到1点直接恐惧。"""
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or (ctx.amount or 0) < 1:
            return
        if self._find_hypochondria(ctx.game_state, inv) is None:
            return
        inv.horror += 1  # 直接恐惧（不分配）

    def activate_discard(self, game_state, investigator_id) -> bool:
        """[action][action]：丢弃忧郁症。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return False
        inst = self._find_hypochondria(game_state, inv)
        if inst is None:
            return False
        inv.threat_area.remove(inst.instance_id)
        game_state.cards_in_play.pop(inst.instance_id, None)
        inv.discard.append("hypochondria")
        return True

    @staticmethod
    def _find_hypochondria(game_state, inv):
        for inst_id in inv.threat_area:
            inst = game_state.get_card_instance(inst_id)
            if inst is not None and inst.card_id == "hypochondria":
                return inst
        return None
