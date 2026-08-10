"""Foresight (Level 1) — Mystic Event. (Augury)
快速。当你所在地点的一位调查员将从其牌库或遭遇牌堆抽1张牌时打出。
指定1张卡。如果抽到的正是指定的卡，该调查员可以（二选一）：
- 取消该卡的效果并弃掉它。
- 立即以-2费用打出该卡。

简化说明：
- 指定卡名经 arm() 预设（无"抽到后再指名"的选择 UI）；命中后默认取消并弃掉
  （mode="cancel"）。arm(mode="play") 时改为立即-2费用打出：仅支持支援卡
  （手动入场，CARD_ENTERS_PLAY 不补发——引擎缺口）；事件卡不支持立即打出，
  回退为取消。
- 同时监听 CARD_DRAWN（调查员牌库）与 ENCOUNTER_CARD_DRAWN（遭遇牌堆）；
  遭遇牌取消记入 scenario.vars["cancelled_encounter"]（同 ward_of_protection）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import CardType, GameEvent, TimingPriority
from backend.models.state import CardInstance


class Foresight(CardImplementation):
    card_id = "foresight_lv1"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._named_card_id: str | None = None
        self._holder_id: str | None = None
        self._mode = "cancel"

    def arm(self, game_state, investigator_id: str, named_card_id: str,
            mode: str = "cancel") -> bool:
        """预设指定卡名（holder 须手牌中有本卡）。mode: cancel / play。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.card_id not in inv.hand:
            return False
        self._named_card_id = named_card_id
        self._holder_id = investigator_id
        self._mode = mode
        return True

    @on_event(GameEvent.CARD_DRAWN, priority=TimingPriority.WHEN)
    def on_deck_draw(self, ctx):
        self._maybe_trigger(ctx, from_encounter=False)

    @on_event(GameEvent.ENCOUNTER_CARD_DRAWN, priority=TimingPriority.WHEN)
    def on_encounter_draw(self, ctx):
        self._maybe_trigger(ctx, from_encounter=True)

    def _maybe_trigger(self, ctx, from_encounter: bool) -> None:
        card_id = ctx.extra.get("card_id")
        if not card_id or card_id != self._named_card_id:
            return
        holder = ctx.game_state.get_investigator(self._holder_id)
        drawer = ctx.game_state.get_investigator(ctx.investigator_id)
        if (holder is None or drawer is None
                or self.card_id not in holder.hand
                or holder.location_id != drawer.location_id):
            return

        # 打出本卡（快速，0费）
        holder.hand.remove(self.card_id)
        holder.discard.append(self.card_id)
        ctx.extra["foresight_triggered"] = card_id
        named = self._named_card_id
        self._named_card_id = None

        cd = ctx.game_state.get_card_data(card_id)
        cost = (cd.cost or 0) if cd else 0
        if (self._mode == "play" and cd is not None
                and cd.type == CardType.ASSET
                and not from_encounter
                and drawer.resources >= max(0, cost - 2)):
            # 立即以-2费用打出（仅支援卡；手动入场，不补发事件——引擎缺口）
            drawer.resources -= max(0, cost - 2)
            if card_id in drawer.hand:
                drawer.hand.remove(card_id)
            inst = CardInstance(
                instance_id=ctx.game_state.next_instance_id(),
                card_id=card_id,
                owner_id=drawer.investigator_id,
                controller_id=drawer.investigator_id,
                slot_used=list(cd.slots or []),
            )
            if cd.uses:
                inst.uses = dict(cd.uses)
            ctx.game_state.cards_in_play[inst.instance_id] = inst
            drawer.play_area.append(inst.instance_id)
            ctx.extra["foresight_played"] = card_id
            return

        # 默认：取消效果并弃掉
        if from_encounter:
            ctx.game_state.scenario.vars["cancelled_encounter"] = card_id
        else:
            if card_id in drawer.hand:
                drawer.hand.remove(card_id)
            drawer.discard.append(card_id)
        ctx.cancel()  # 取消该卡效果（中断后续 draw 处理）
        ctx.extra["foresight_cancelled"] = card_id
