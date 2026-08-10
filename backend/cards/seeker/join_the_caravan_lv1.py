"""Join the Caravan (Level 1) — Seeker Event, Fast. (08036)
快速。只能在你的回合中打出。你控制的卡牌之中每有一个不同的职阶，
本卡牌的费用减1。移动到任一个已揭示地点。

简化说明：
- 引擎出牌流程直接读取 card_data.cost（无动态费用钩子，引擎缺口），
  故费用减免实现为"打出后返还"：返还 = min(你控制卡牌的不同职阶数, 5)，
  净支出与官方一致；但资源不足全额5点时无法打出（引擎缺口，见报告）；
- "只能在你的回合中打出"的时机校验由会话层负责；
- 目标地点默认为第一个非当前地点的已揭示地点（官方为玩家自选任意已揭示
  地点）；可用 ctx.extra["destination"] 指定；
- 移动不携带交战敌人（引擎 _move 同款简化）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority

_FULL_COST = 5


class JoinTheCaravan(CardImplementation):
    card_id = "join_the_caravan_lv1"

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def discount_and_move(self, ctx):
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return

        # 费用减免（返还）：你控制卡牌的不同职阶数
        classes = set()
        for iid in inv.play_area:
            inst = ctx.game_state.get_card_instance(iid)
            cd = ctx.game_state.get_card_data(inst.card_id) if inst else None
            if cd is not None and cd.card_class is not None:
                classes.add(cd.card_class)
        refund = min(len(classes), _FULL_COST)
        if refund:
            inv.resources += refund
            ctx.extra["join_the_caravan_refund"] = refund

        # 移动到任一已揭示地点
        destination = ctx.extra.get("destination")
        if destination is None:
            for loc_id, loc in ctx.game_state.locations.items():
                if loc_id != inv.location_id and loc.revealed:
                    destination = loc_id
                    break
        target = ctx.game_state.get_location(destination) if destination else None
        if target is None or not target.revealed:
            return
        inv.location_id = destination
        ctx.extra["join_the_caravan_moved_to"] = destination
        ctx.game_state.log_effect(
            f"🐪 加入商队：移动到【{target.card_data.name_cn or target.card_data.name}】"
        )
