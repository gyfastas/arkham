"""Ice Pick (Level 3) — Seeker Asset, Hand slot. (08107)
快速。
[快速]攻击或调查时的技能检定中，消耗破冰锥：你这次检定+1技能值。如果你
成功，你可以丢弃破冰锥来使这次攻击造成+1伤害（如果你攻击），或发现你
所在地点额外1个线索（如果你调查）。

简化说明：
- +1技能值机制与 lv1 相同（use() 消耗并武装）；
- "你可以丢弃"为自动触发（官方为玩家选择；与 lucky 等卡的自动简化一致）：
  攻击成功 → 丢弃本卡，经 ctx.extra["bonus_damage"] 汇入+1伤害
  （与 shrivelling 一致）；调查成功 → 基础发现的 CLUE_DISCOVERED 结算后
  丢弃本卡并多取1线索（与 deduction 的次序一致，地点无线索则不丢弃）。
"""

from backend.cards.base import on_event
from backend.cards.seeker.ice_pick_lv1 import IcePick
from backend.engine.slots import vacate_asset_slots
from backend.models.enums import GameEvent, TimingPriority


class IcePickLv3(IcePick):
    card_id = "ice_pick_lv3"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._clue_pending: str | None = None

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.WHEN)
    def cash_in_on_success(self, ctx):
        """成功后丢弃本卡：攻击+1伤害；调查标记待取额外线索。"""
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        if self._is_armed_fight(ctx):
            self._discard_self(ctx)
            ctx.extra["bonus_damage"] = ctx.extra.get("bonus_damage", 0) + 1
            ctx.game_state.log_effect("⛏️ 破冰锥：丢弃，本次攻击+1伤害")
        elif self._is_armed_investigate(ctx):
            self._clue_pending = ctx.investigator_id

    @on_event(GameEvent.CLUE_DISCOVERED, priority=TimingPriority.AFTER)
    def take_extra_clue(self, ctx):
        """调查的基础发现结算后：丢弃本卡，额外发现1个线索。"""
        if self._clue_pending != ctx.investigator_id:
            return
        self._clue_pending = None
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        location = ctx.game_state.get_location(inv.location_id)
        if location is None or location.clues <= 0:
            return
        self._discard_self(ctx)
        location.clues -= 1
        inv.clues += 1
        ctx.extra["ice_pick_extra_clue"] = True
        ctx.game_state.log_effect("⛏️ 破冰锥：丢弃，额外发现1个线索")

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear_pending(self, ctx):
        self._clue_pending = None

    def _discard_self(self, ctx) -> None:
        """丢弃破冰锥（腾出槽位、离场入弃牌堆）。"""
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        vacate_asset_slots(ctx.game_state, self.instance_id)
        inv.play_area.remove(self.instance_id)
        ctx.game_state.cards_in_play.pop(self.instance_id, None)
        inv.discard.append(self.card_id)
