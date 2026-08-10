"""Cheat Death (Level 5) — Rogue Event.
快速。在你将要被击败时打出。
解除与每个和你交战敌人的交战状态，丢弃你威胁区域中的所有卡牌，
治愈2点恐惧和2点伤害，并移动到任意一个没有敌人的已揭示地点。
如果这是你的回合，结束你的回合。从游戏中移除死里逃生。

简化说明：
- 从手牌中自动触发：你将被击败（INVESTIGATOR_DEFEATED）时，若手牌中有
  本卡且能支付1资源，自动打出并结算（官方为玩家自行选择打出时机）。
- "从游戏中移除"：不进入弃牌堆（打出后直接移出游戏）。
- 移动目标自动选择第一个没有敌人的已揭示地点，可用 ctx.extra["destination"]
  指定（官方为玩家自选）；若不存在符合条件的地点则不移动。
- "结束你的回合"近似为 actions_remaining=0（引擎无回合中断通道）。
- 治愈后被击败状态可能解除（伤害/恐惧降到阈值下）；仍高于阈值时
  官方也无法免死，本卡效果照常结算。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority
from backend.models.enums import CardType


class CheatDeath(CardImplementation):
    card_id = "cheat_death_lv5"
    persistent_in_hand = True  # 在手牌中持续监听"将要被击败"窗口

    @on_event(GameEvent.INVESTIGATOR_DEFEATED, priority=TimingPriority.WHEN)
    def cheat_death(self, ctx):
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.card_id not in inv.hand:
            return

        # 自动打出（简化：官方为玩家选择时机）
        cd = ctx.game_state.get_card_data(self.card_id)
        cost = (getattr(cd, "cost", 1) or 1) if cd else 1
        if inv.resources < cost:
            return
        inv.resources -= cost
        inv.hand.remove(self.card_id)  # 从游戏中移除：不入弃牌堆

        # 解除交战：交战敌人放回当前地点
        cur_loc = ctx.game_state.get_location(inv.location_id)
        for enemy_iid in list(inv.threat_area):
            inst = ctx.game_state.get_card_instance(enemy_iid)
            ed = ctx.game_state.get_card_data(inst.card_id) if inst else None
            if ed is not None and ed.type == CardType.ENEMY:
                inv.threat_area.remove(enemy_iid)
                if cur_loc is not None and enemy_iid not in cur_loc.enemies:
                    cur_loc.enemies.append(enemy_iid)

        # 丢弃威胁区域中的所有（非敌人）卡牌
        for card_iid in list(inv.threat_area):
            inst = ctx.game_state.get_card_instance(card_iid)
            if inst is None:
                inv.threat_area.remove(card_iid)
                continue
            inv.threat_area.remove(card_iid)
            ctx.game_state.cards_in_play.pop(card_iid, None)
            inv.discard.append(inst.card_id)

        # 治愈2点恐惧和2点伤害
        inv.damage = max(0, inv.damage - 2)
        inv.horror = max(0, inv.horror - 2)

        # 移动到任意一个没有敌人的已揭示地点
        destination = ctx.extra.get("destination")
        if destination is None:
            for loc_id, loc in ctx.game_state.locations.items():
                if loc_id == inv.location_id:
                    continue
                if loc.revealed and not loc.enemies:
                    destination = loc_id
                    break
        if destination is not None and destination in ctx.game_state.locations:
            dest = ctx.game_state.get_location(destination)
            if dest.revealed and not dest.enemies:
                inv.location_id = destination
                ctx.extra["cheat_death_moved_to"] = destination

        # 如果这是你的回合，结束你的回合（近似：清空剩余行动）
        inv.actions_remaining = 0

        ctx.extra["cheat_death_saved"] = True
        ctx.game_state.log_effect("😇 死里逃生：免死，治愈2/2并转移")
