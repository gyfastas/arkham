"""Recharge (Level 2) — Mystic Event. (03197)
选择你所在地点的一位调查员控制的一张[[法术]]或[[遗物]]支援卡，并从混乱袋中
随机揭示1个混乱标记。如果揭示了[skull]、[cultist]、[tablet]、[elder_thing]
或[auto_fail]标记，丢弃选择的支援卡。否则，为选择的支援卡增加3点充能。

简化说明：
- 目标自动选择：你所在地点调查员控制的第一张带充能的法术/遗物支援
  （无选择 UI；优先你自己控制的）；可用 ctx.extra["target_instance_id"] 指定。
- 混沌袋经 bind_chaos_bag() 注入（registry.activate_card 自动接线）；未绑定时
  退化为独立随机标准袋。
- 丢弃目标时手动移出场地（卡牌代码拿不到事件总线，CARD_LEAVES_PLAY 不补发，
  同 grotesque_statue 惯例）。
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


class Recharge(CardImplementation):
    card_id = "recharge_lv2"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._chaos_bag = None
        self._rng = random.Random()

    def bind_chaos_bag(self, chaos_bag) -> None:
        """注入游戏混沌袋（registry.activate_card 自动调用）。"""
        self._chaos_bag = chaos_bag

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def resolve(self, ctx):
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return

        target = self._find_target(ctx, inv)
        if target is None:
            return
        ctx.extra["recharge_target"] = target.instance_id

        # 揭示1个随机混乱标记
        if self._chaos_bag is not None:
            token = self._chaos_bag.draw()
        else:
            token = self._rng.choice(list(STANDARD_BAG))
        ctx.extra["recharge_token"] = getattr(token, "value", str(token))

        if token in _BAD_TOKENS:
            # 丢弃选择的支援卡
            owner = ctx.game_state.get_investigator(target.owner_id)
            vacate_asset_slots(ctx.game_state, target.instance_id)
            if owner is not None and target.instance_id in owner.play_area:
                owner.play_area.remove(target.instance_id)
                owner.discard.append(target.card_id)
            ctx.game_state.cards_in_play.pop(target.instance_id, None)
            ctx.extra["recharge_discarded"] = target.card_id
            ctx.game_state.log_effect(
                f"⚡ 充能：坏标记，丢弃【{ctx.game_state.card_name(target.card_id)}】")
        else:
            target.uses["charges"] = target.uses.get("charges", 0) + 3
            ctx.extra["recharge_charges_added"] = 3
            ctx.game_state.log_effect(
                f"⚡ 充能：【{ctx.game_state.card_name(target.card_id)}】+3充能")

    def _find_target(self, ctx, inv):
        """目标：你所在地点调查员控制的法术/遗物支援（优先自己、优先带充能）。"""
        target_iid = ctx.extra.get("target_instance_id")
        investigators = ctx.game_state.get_investigators_at_location(inv.location_id)
        # 自己优先
        investigators.sort(
            key=lambda i: i.investigator_id != inv.investigator_id)

        candidates = []
        for candidate_inv in investigators:
            for iid in candidate_inv.play_area:
                ci = ctx.game_state.get_card_instance(iid)
                if ci is None:
                    continue
                cd = ctx.game_state.get_card_data(ci.card_id)
                traits = [t.lower() for t in (cd.traits or [])] if cd else []
                if "spell" in traits or "relic" in traits:
                    candidates.append(ci)
        if target_iid is not None:
            for ci in candidates:
                if ci.instance_id == target_iid:
                    return ci
            return None
        # 默认：优先带充能的（+3充能才有意义）
        with_charges = [ci for ci in candidates if "charges" in ci.uses]
        return (with_charges or candidates or [None])[0]
