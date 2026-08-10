"""Investments (Level 0) — Rogue Asset. (05233)
使用(0补给)。投资上至多存放10补给。
[快速]消耗投资：在其上放置1补给。
[行动]消耗并弃置投资：将其上所有补给移至你的资源池，视为资源。

简化说明：
- 两个能力均为公开方法（store / cash_out），由 UI/会话层调用；
  activations 声明行动费（store 快速0行动，cash_out 1行动）。
- 数据 uses 键兼容双 s 写法（"suppliess"）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.engine.slots import vacate_asset_slots
from backend.models.enums import GameEvent, TimingPriority

_MAX_SUPPLIES = 10


def _uses_key(inst, key: str) -> str:
    """兼容源数据复数化笔误（"suppliess"）。"""
    if key in inst.uses:
        return key
    alt = f"{key}s"
    return alt if alt in inst.uses else key


class Investments(CardImplementation):
    card_id = "investments_lv0"
    activations = [
        {"id": "store", "label": "消耗：放置1补给", "method": "store",
         "actions": 0},
        {"id": "cash_out", "label": "消耗并弃置：补给转为资源",
         "method": "cash_out", "actions": 1},
    ]

    def store(self, game_state, investigator_id: str) -> bool:
        """[快速]消耗：在本卡上放置1补给（至多10）。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None or inst.exhausted:
            return False
        key = _uses_key(inst, "supplies")
        if inst.uses.get(key, 0) >= _MAX_SUPPLIES:
            return False
        inst.exhausted = True
        inst.uses[key] = inst.uses.get(key, 0) + 1
        return True

    def cash_out(self, game_state, investigator_id: str) -> bool:
        """[行动]消耗并弃置：本卡上所有补给转为你的资源。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None:
            return False
        key = _uses_key(inst, "supplies")
        payout = inst.uses.get(key, 0)
        inv.resources += payout

        # 弃置本卡（含槽位释放与离场事件）
        vacate_asset_slots(game_state, self.instance_id)
        if self.instance_id in inv.play_area:
            inv.play_area.remove(self.instance_id)
        inv.discard.append(self.card_id)
        game_state.cards_in_play.pop(self.instance_id, None)
        from backend.engine.event_bus import EventContext
        bus = getattr(self, "_bus", None)
        if bus is not None:
            bus.emit(EventContext(
                game_state=game_state,
                event=GameEvent.CARD_LEAVES_PLAY,
                investigator_id=investigator_id,
                target=self.instance_id,
                extra={"card_id": self.card_id},
            ))
        game_state.log_effect(f"💰 投资兑现：{payout}补给转为资源")
        return True

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus
