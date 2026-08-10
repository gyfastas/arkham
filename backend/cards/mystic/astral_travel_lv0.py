"""Astral Travel (Level 0) — Mystic Event. (03034)
<b>移动</b>。移动到任意一个已揭示的地点，并从混乱袋中随机揭示1个标记。
如果揭示了[skull]、[cultist]、[tablet]、[elder_thing]或[auto_fail]标记，
你必须丢弃一张你控制的[[道具]]或[[盟友]]支援卡（若不能，则受到1点伤害）。

简化说明：
- 目标地点自动选择：第一个非当前地点的已揭示地点（官方为玩家自选任意已揭示
  地点）；可用 ctx.extra["destination"] 指定。
- 坏标记时丢弃的支援自动选第一张道具/盟友（官方为玩家自选）；可用
  ctx.extra["discard_instance_id"] 指定。
- 混沌袋经 bind_chaos_bag() 注入（registry.activate_card 自动接线）；未绑定时
  退化为独立随机标准袋。
- 移动不携带交战敌人（引擎 _move 同款简化）。
"""

import random

from backend.cards.base import CardImplementation, on_event
from backend.engine.slots import vacate_asset_slots
from backend.models.chaos import STANDARD_BAG
from backend.models.enums import ChaosTokenType, GameEvent, TimingPriority

_BAD_TOKENS = {
    ChaosTokenType.SKULL, ChaosTokenType.CULTIST,
    ChaosTokenType.TABLET, ChaosTokenType.ELDER_THING,
    ChaosTokenType.AUTO_FAIL,
}


class AstralTravel(CardImplementation):
    card_id = "astral_travel_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._chaos_bag = None
        self._rng = random.Random()

    def bind_chaos_bag(self, chaos_bag) -> None:
        """注入游戏混沌袋（registry.activate_card 自动调用）。"""
        self._chaos_bag = chaos_bag

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def move_and_reveal(self, ctx):
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return

        # 移动到任意已揭示地点
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
        ctx.extra["astral_travel_moved_to"] = destination

        # 从混乱袋揭示1个随机标记
        if self._chaos_bag is not None:
            token = self._chaos_bag.draw()
        else:
            token = self._rng.choice(list(STANDARD_BAG))
        ctx.extra["astral_travel_token"] = getattr(token, "value", str(token))

        if token not in _BAD_TOKENS:
            return

        # 坏标记：丢弃一张你控制的道具/盟友支援，否则受到1点伤害
        discard_iid = ctx.extra.get("discard_instance_id")
        candidates = []
        for iid in inv.play_area:
            ci = ctx.game_state.get_card_instance(iid)
            if ci is None:
                continue
            cd = ctx.game_state.get_card_data(ci.card_id)
            traits = [t.lower() for t in (cd.traits or [])] if cd else []
            if "item" in traits or "ally" in traits:
                candidates.append(iid)
        if discard_iid is not None and discard_iid not in candidates:
            discard_iid = None
        if discard_iid is None and candidates:
            discard_iid = candidates[0]

        if discard_iid is None:
            inv.damage += 1
            ctx.extra["astral_travel_damage"] = 1
            return

        ci = ctx.game_state.get_card_instance(discard_iid)
        vacate_asset_slots(ctx.game_state, discard_iid)
        inv.play_area.remove(discard_iid)
        inv.discard.append(ci.card_id)
        ctx.game_state.cards_in_play.pop(discard_iid, None)
        ctx.extra["astral_travel_discarded"] = ci.card_id
        ctx.game_state.log_effect(
            f"🌌 星界旅行：坏标记，丢弃【{ctx.game_state.card_name(ci.card_id)}】")
        # 注：卡牌代码拿不到事件总线，CARD_LEAVES_PLAY 不再补发
        # （与 grotesque_statue 的手动移除同款简化）。
