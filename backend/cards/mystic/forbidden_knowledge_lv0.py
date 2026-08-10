"""Forbidden Knowledge (Level 0) — Mystic Asset. (01058)
使用(4个秘密)。如果禁忌知识上没有秘密，弃置它。
[fast] 横置禁忌知识并受到1点恐惧：将禁忌知识上的1个秘密移动到你的资源池，
作为1个资源。
"""

from backend.cards.base import CardImplementation, on_event
from backend.engine.slots import vacate_asset_slots
from backend.models.enums import GameEvent, TimingPriority


class ForbiddenKnowledge(CardImplementation):
    card_id = "forbidden_knowledge_lv0"
    activations = [{
        "id": "secret",
        "label": "【快速】横置+受1恐惧：1秘密换1资源",
        "method": "activate",
    }]

    @on_event(GameEvent.CARD_ENTERS_PLAY, priority=TimingPriority.AFTER)
    def enter_play(self, ctx):
        """进场时：带有4个秘密（数据 uses 未初始化时兜底）。"""
        if ctx.target != self.instance_id:
            return
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is not None and "secrets" not in inst.uses:
            inst.uses["secrets"] = 4

    def activate(self, game_state, investigator_id: str) -> bool:
        """【快速】横置并受到1点恐惧：将1个秘密转为1个资源。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None or inst.exhausted or inst.uses.get("secrets", 0) <= 0:
            return False
        inst.exhausted = True
        inst.uses["secrets"] -= 1
        inv.horror += 1
        inv.resources += 1
        self._discard_if_empty(game_state, inv)
        return True

    def _discard_if_empty(self, game_state, inv) -> None:
        """没有秘密时：弃置禁忌知识。"""
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None or inst.uses.get("secrets", 0) > 0:
            return
        vacate_asset_slots(game_state, self.instance_id)
        if self.instance_id in inv.play_area:
            inv.play_area.remove(self.instance_id)
        inv.discard.append(self.card_id)
        game_state.cards_in_play.pop(self.instance_id, None)
