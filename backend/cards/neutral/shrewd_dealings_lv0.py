"""Shrewd Dealings (Level 0) — Neutral Asset. (08017)
仅限鲍勃·詹金斯牌组。
你打出的每张[[物品]]支援卡费用降低1。
[reaction]当你打出一张[[物品]]支援卡时：在你所在地点的任意一名调查员的
控制下打出它。

简化说明：
- "仅限鲍勃牌组"为构筑限制，由卡组校验负责。
- 费用降低实现为打出后返还1资源（引擎在 CARD_ENTERS_PLAY 前已全额扣费，
  无打出前改费通道；同 rod_of_animalism_lv1 惯例）。
- 控制权转移为可选反应：会话层在玩家选择其他调查员时调用
  transfer_last_item()；缺省不转移（留在打出者控制下）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import CardType, GameEvent, TimingPriority


class ShrewdDealings(CardImplementation):
    card_id = "shrewd_dealings_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._last_item_id: str | None = None

    @on_event(GameEvent.CARD_ENTERS_PLAY, priority=TimingPriority.AFTER)
    def refund_item_cost(self, ctx):
        """打出物品支援卡：返还1资源。"""
        if ctx.target == self.instance_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        cd = ctx.game_state.get_card_data(ctx.extra.get("card_id"))
        if cd is None or cd.type != CardType.ASSET:
            return
        if "item" not in (cd.traits or []):
            return
        if (cd.cost or 0) >= 1:
            inv.resources += 1
            ctx.extra["shrewd_dealings_refund"] = 1
        self._last_item_id = ctx.target

    def transfer_last_item(self, game_state, target_investigator_id: str) -> bool:
        """[reaction]：将刚打出的物品转交给同地点的另一名调查员控制。"""
        if self._last_item_id is None:
            return False
        inst = game_state.get_card_instance(self._last_item_id)
        if inst is None:
            return False
        source = game_state.get_investigator(inst.controller_id)
        target = game_state.get_investigator(target_investigator_id)
        if source is None or target is None or target is source:
            return False
        if target.location_id != source.location_id:
            return False
        if inst.instance_id in source.play_area:
            source.play_area.remove(inst.instance_id)
        target.play_area.append(inst.instance_id)
        inst.controller_id = target.investigator_id
        self._last_item_id = None
        return True
