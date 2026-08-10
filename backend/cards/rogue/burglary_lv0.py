"""Burglary (Level 0) — Rogue Asset.
消耗夜盗：调查。如果你成功，获得3资源而不是发现线索。

简化说明：
- activate() 消耗本卡并武装；随后由会话层发起调查行动
  （武装后下一次调查成功即转换，若先做了其他检定则武装在
  SKILL_TEST_ENDS 时清除）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class Burglary(CardImplementation):
    card_id = "burglary_lv0"
    activations = [{"id": "investigate", "label": "消耗：调查，成功改为拿3资源", "method": "activate"}]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._armed = False

    def activate(self, game_state, investigator_id: str) -> bool:
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None or inst.exhausted:
            return False
        inst.exhausted = True
        self._armed = True
        return True

    @on_event(GameEvent.CLUE_DISCOVERED, priority=TimingPriority.WHEN)
    def resources_instead(self, ctx):
        """成功：获得3资源而不是发现线索（事后校正）。"""
        if not self._armed:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        loc = ctx.game_state.get_location(ctx.location_id or inv.location_id)
        if loc is not None:
            loc.clues += 1  # 返还线索
        inv.clues = max(0, inv.clues - 1)
        inv.resources += 3
        ctx.extra["burglary_resources"] = True

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._armed = False
