"""Burn After Reading (Level 1) — Survivor Event.
放逐你手中1张等级0-5的卡牌。发现你所在地点的2个线索。
若被放逐的卡牌等级为2或更高，从当前密谋移除1个毁灭标记。放逐阅后即焚。

简化说明：
- 放逐目标自动选择手中第一张等级0-5的卡牌（可经 ctx.extra["exile_card_id"]
  指定）；官方为玩家选择。
- 放逐区沿用既有约定 scenario.vars["exiled_cards"]（引擎无独立放逐区）。
- 地点线索不足2个时按实际数量发现。
- "放逐阅后即焚"：引擎在 CARD_PLAYED 结算后才把事件放入弃牌堆，延迟到
  ROUND_ENDS 从弃牌堆移至放逐区（eidetic_memory 同模式）。
- "从当前密谋移除1个毁灭"按 scenario.doom_on_agenda 结算。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class BurnAfterReading(CardImplementation):
    card_id = "burn_after_reading_lv1"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._exile_self_for: str | None = None

    def _choose_exile_target(self, ctx, inv) -> str | None:
        wanted = ctx.extra.get("exile_card_id")
        if wanted:
            cd = ctx.game_state.get_card_data(wanted)
            if wanted in inv.hand and cd is not None and 0 <= (cd.level or 0) <= 5:
                return wanted
            return None
        for cid in inv.hand:
            cd = ctx.game_state.get_card_data(cid)
            if cd is not None and 0 <= (cd.level or 0) <= 5:
                return cid
        return None

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def exile_and_discover(self, ctx):
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        self._exile_self_for = ctx.investigator_id

        target_id = self._choose_exile_target(ctx, inv)
        if target_id is None:
            ctx.game_state.log_effect("🔥 阅后即焚：手中没有可放逐的卡牌")
            return
        target_cd = ctx.game_state.get_card_data(target_id)
        inv.hand.remove(target_id)
        ctx.game_state.scenario.vars.setdefault("exiled_cards", []).append(target_id)

        # 发现所在地点的2个线索
        loc = ctx.game_state.get_location(inv.location_id)
        found = 0
        if loc is not None:
            found = min(2, loc.clues)
            loc.clues -= found
            inv.clues += found

        # 被放逐卡等级≥2：当前密谋移除1毁灭
        doom_removed = False
        if (getattr(target_cd, "level", 0) or 0) >= 2:
            scenario = ctx.game_state.scenario
            if scenario.doom_on_agenda > 0:
                scenario.doom_on_agenda -= 1
                doom_removed = True

        ctx.extra["burn_after_reading_exiled"] = target_id
        ctx.extra["burn_after_reading_clues"] = found
        ctx.game_state.log_effect(
            f"🔥 阅后即焚：放逐【{ctx.game_state.card_name(target_id)}】，"
            f"发现{found}个线索" + ("，密谋移除1毁灭" if doom_removed else ""))

    @on_event(GameEvent.ROUND_ENDS, priority=TimingPriority.AFTER)
    def exile_self(self, ctx):
        """本卡以放逐代替弃置（出牌结算后才进弃牌堆，延迟清理）。"""
        if self._exile_self_for is None:
            return
        inv = ctx.game_state.get_investigator(self._exile_self_for)
        self._exile_self_for = None
        if inv is not None and self.card_id in inv.discard:
            inv.discard.remove(self.card_id)
            ctx.game_state.scenario.vars.setdefault(
                "exiled_cards", []).append(self.card_id)
