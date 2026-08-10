"""Connect the Dots (Level 0) — Seeker Event, Fast. (05025)
快速。在你发现你所在地点的最后1条线索后打出。
在一个印刷隐蔽值低于你所在地点的地点发现2条线索。

简化说明：
- 从手牌自动触发并打出（官方为玩家选择打出时机，与 lucky/forewarned 同款
  手牌自动打出模式）：你发现所在地点最后1条线索（地点线索归零）后，若手牌
  中有本卡且资源足够，自动支付费用打出；
- 目标地点自动选择印刷隐蔽值更低且仍有线索的地点中线索最多者（官方为玩家
  自选）；不足2条线索时尽力发现；
- 无合法目标地点时不打出。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority

CLUES_TO_DISCOVER = 2


class ConnectTheDots(CardImplementation):
    card_id = "connect_the_dots_lv0"
    persistent_in_hand = True  # 手牌中持续监听"发现最后1条线索"

    @on_event(GameEvent.CLUE_DISCOVERED, priority=TimingPriority.AFTER)
    def auto_play(self, ctx):
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.card_id not in inv.hand:
            return
        loc = ctx.game_state.get_location(ctx.location_id or inv.location_id)
        if loc is None or loc.clues > 0:
            return  # 尚有线索：非"最后1条"
        cd = ctx.game_state.get_card_data(self.card_id)
        cost = (getattr(cd, "cost", 4) or 4) if cd else 4
        if inv.resources < cost:
            return

        target = self._choose_target(ctx.game_state, loc)
        if target is None:
            return

        # 自动打出（快速，不耗行动）
        inv.resources -= cost
        inv.hand.remove(self.card_id)
        inv.discard.append(self.card_id)

        found = min(CLUES_TO_DISCOVER, target.clues)
        target.clues -= found
        inv.clues += found
        ctx.extra["connect_the_dots_played"] = target.location_id
        ctx.game_state.log_effect(
            f"🔗 串联线索：自动打出，在"
            f"【{self._loc_name(ctx.game_state, target)}】发现{found}条线索"
        )

    @staticmethod
    def _choose_target(game_state, origin):
        """印刷隐蔽值更低且仍有线索的地点中，线索最多者（并列取先发现者）。"""
        printed = origin.shroud
        best = None
        for loc in game_state.locations.values():
            if loc.location_id == origin.location_id:
                continue
            if loc.clues <= 0 or loc.shroud >= printed:
                continue
            if best is None or loc.clues > best.clues:
                best = loc
        return best

    @staticmethod
    def _loc_name(game_state, loc) -> str:
        cd = getattr(loc, "card_data", None)
        return (cd.name_cn or cd.name) if cd else loc.location_id
