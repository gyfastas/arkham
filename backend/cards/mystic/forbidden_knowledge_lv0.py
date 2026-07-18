"""Forbidden Knowledge (Level 0) — Mystic Asset.
禁忌知识进场时带有4个秘密。
反应 - 在禁忌知识上有秘密时：花费1秘密并受到1点恐惧，获得2资源。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class ForbiddenKnowledge(CardImplementation):
    card_id = "forbidden_knowledge_lv0"
    activations = [{"id": "secret", "label": "花1秘密受1恐惧：获得2资源", "method": "activate"}]

    @on_event(GameEvent.CARD_ENTERS_PLAY, priority=TimingPriority.AFTER)
    def enter_play(self, ctx):
        """进场时：放置4个秘密。"""
        if ctx.target != self.instance_id:
            return
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is not None:
            inst.uses["secret"] = 4

    def activate(self, game_state, investigator_id: str) -> bool:
        """花费1秘密并受到1点恐惧，获得2资源。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None or inst.uses.get("secret", 0) <= 0:
            return False
        inst.uses["secret"] -= 1
        inv.horror += 1
        inv.resources += 2
        return True
