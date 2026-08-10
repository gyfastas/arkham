"""Winds of Power (Level 1) — Mystic Event. (08063)
在你控制的一张支援卡上放置2充能。
[reaction] 在你的回合中抽取本卡后：打出本卡。

简化说明：
- 目标自动选择：优先你控制的第一张已带充能的支援卡，否则第一张支援卡
  （无选择 UI；数据笔误的 "chargess" 键经 seeker._uses 兼容）。
- 抽到即打出为自动触发（官方为玩家选择的反应）：跟踪
  INVESTIGATOR_TURN_BEGINS/ENDS 判断"你的回合中"；资源不足支付费用时
  不自动打出（留在手牌）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.cards.seeker._uses import uses_count, uses_key
from backend.models.enums import GameEvent, TimingPriority


class WindsOfPower(CardImplementation):
    card_id = "winds_of_power_lv1"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._in_turn: set[str] = set()

    @on_event(GameEvent.INVESTIGATOR_TURN_BEGINS, priority=TimingPriority.AFTER)
    def track_turn_begin(self, ctx):
        if ctx.investigator_id:
            self._in_turn.add(ctx.investigator_id)

    @on_event(GameEvent.INVESTIGATOR_TURN_ENDS, priority=TimingPriority.AFTER)
    def track_turn_end(self, ctx):
        self._in_turn.discard(ctx.investigator_id)

    @on_event(GameEvent.CARD_DRAWN, priority=TimingPriority.AFTER)
    def autoplay_on_draw(self, ctx):
        """你的回合中抽到：自动打出（支付费用）。"""
        if ctx.extra.get("card_id") != self.card_id:
            return
        if ctx.investigator_id not in self._in_turn:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.card_id not in inv.hand:
            return
        cd = ctx.game_state.get_card_data(self.card_id)
        cost = (cd.cost or 0) if cd else 0
        if inv.resources < cost:
            ctx.game_state.log_effect("🌬 力量之风：资源不足，无法自动打出")
            return
        inv.resources -= cost
        inv.hand.remove(self.card_id)
        self._place_charges(ctx.game_state, inv, ctx)
        inv.discard.append(self.card_id)
        ctx.game_state.log_effect("🌬 力量之风：回合中抽到，自动打出")

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def on_played(self, ctx):
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is not None:
            self._place_charges(ctx.game_state, inv, ctx)

    def _place_charges(self, game_state, inv, ctx) -> None:
        """在你控制的一张支援卡上放置2充能（自动选择，见 docstring）。"""
        target = None
        fallback = None
        for iid in inv.play_area:
            ci = game_state.get_card_instance(iid)
            if ci is None:
                continue
            if fallback is None:
                fallback = ci
            if uses_count(ci, "charges") > 0:
                target = ci
                break
        if target is None:
            target = fallback
        if target is None:
            game_state.log_effect("🌬 力量之风：没有可放置充能的支援卡")
            return
        key = uses_key(target, "charges")
        target.uses[key] = uses_count(target, "charges") + 2
        ctx.extra["winds_of_power_target"] = target.instance_id
        game_state.log_effect(
            f"🌬 力量之风：【{game_state.card_name(target.card_id)}】+2充能")
