"""Teamwork (Level 0) — Guardian Event.
你所在地点的调查员，可以自由给予或交易任意数量的[道具]支援卡、
[盟友]支援卡和资源。

简化说明：
- 交易是多人交互效果，实现为 activate_trade() 公开方法（资源转账），
  卡牌/支援卡的交易由会话层 UI 驱动后调用。单人游戏为无操作。
"""

from backend.cards.base import CardImplementation, on_event
from backend.engine.slots import vacate_asset_slots
from backend.models.enums import GameEvent, TimingPriority


class Teamwork(CardImplementation):
    card_id = "teamwork_lv0"

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def mark_window(self, ctx):
        if ctx.extra.get("card_id") != "teamwork_lv0":
            return
        ctx.extra["teamwork_active"] = True

    @staticmethod
    def trade_resources(game_state, from_investigator_id: str,
                        to_investigator_id: str, amount: int) -> bool:
        """在同地点调查员之间转移资源。"""
        if amount <= 0:
            return False
        giver = game_state.get_investigator(from_investigator_id)
        receiver = game_state.get_investigator(to_investigator_id)
        if giver is None or receiver is None:
            return False
        if giver.location_id != receiver.location_id:
            return False
        if giver.resources < amount:
            return False
        giver.resources -= amount
        receiver.resources += amount
        return True

    @staticmethod
    def trade_asset(game_state, from_investigator_id: str,
                    to_investigator_id: str, asset_instance_id: str) -> bool:
        """在同地点调查员之间转移1张支援卡（道具/盟友）。"""
        giver = game_state.get_investigator(from_investigator_id)
        receiver = game_state.get_investigator(to_investigator_id)
        if giver is None or receiver is None:
            return False
        if giver.location_id != receiver.location_id:
            return False
        if asset_instance_id not in giver.play_area:
            return False
        inst = game_state.get_card_instance(asset_instance_id)
        if inst is None:
            return False
        data = game_state.get_card_data(inst.card_id)
        traits = set(getattr(data, "traits", []) or []) if data else set()
        if data is not None and not ({"item", "ally"} & traits):
            return False
        vacate_asset_slots(game_state, asset_instance_id)
        giver.play_area.remove(asset_instance_id)
        receiver.play_area.append(asset_instance_id)
        # 交易只改变控制权，所有权不变（官方规则：control 与 ownership 分离）
        inst.controller_id = to_investigator_id
        manager = getattr(game_state, "slot_managers", {}).get(to_investigator_id)
        if manager:
            manager.occupy(asset_instance_id, inst.slot_used)
        return True
