"""Five of Pentacles (Level 1) — Survivor Asset, Tarot slot.
你获得+1生命值和+1神智值。
[反应] 游戏开始时，若星币五在你的起始手牌中：将其放置入场。

简化说明：
- +1生命/+1神智经 health_bonus/sanity_bonus 实现：CARD_ENTERS_PLAY 应用、
  CARD_LEAVES_PLAY 移除（按实例记录，避免起手直入与正常打出双重计数）。
- 起始手牌入场（persistent_in_hand）：SETUP 阶段抽到本卡时自动放置入场
  （占用塔罗槽），与正常打出同走 CARD_ENTERS_PLAY 通道。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Phase, SlotType, TimingPriority
from backend.models.state import CardInstance

_VARS_KEY = "five_of_pentacles_applied"  # {instance_id: owner_id}


class FiveOfPentacles(CardImplementation):
    card_id = "five_of_pentacles_lv1"
    persistent_in_hand = True  # 起始手牌放置入场窗口

    @on_event(GameEvent.CARD_DRAWN, priority=TimingPriority.WHEN)
    def put_into_play_at_setup(self, ctx):
        """游戏开始（SETUP 阶段抽牌）时从起始手牌放置入场。"""
        if ctx.extra.get("card_id") != self.card_id:
            return
        if ctx.game_state.scenario.current_phase != Phase.SETUP:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.card_id not in inv.hand:
            return
        cd = ctx.game_state.get_card_data(self.card_id)
        slots = list(getattr(cd, "slots", None) or [SlotType.TAROT])

        inv.hand.remove(self.card_id)
        iid = ctx.game_state.next_instance_id()
        ctx.game_state.cards_in_play[iid] = CardInstance(
            instance_id=iid,
            card_id=self.card_id,
            owner_id=inv.investigator_id,
            controller_id=inv.investigator_id,
            slot_used=slots,
        )
        inv.play_area.append(iid)
        slot_mgr = getattr(ctx.game_state, "slot_managers", {}).get(
            inv.investigator_id)
        if slot_mgr is not None and slots:
            slot_mgr.occupy(iid, slots, getattr(cd, "traits", None))

        from backend.engine.event_bus import EventContext
        ctx.game_state.log_effect("🔮 星币五：起始手牌放置入场")
        # 走统一的入场通道应用+1/+1
        bus = getattr(self, "_bus", None)
        if bus is not None:
            bus.emit(EventContext(
                game_state=ctx.game_state,
                event=GameEvent.CARD_ENTERS_PLAY,
                investigator_id=inv.investigator_id,
                target=iid,
                extra={"card_id": self.card_id},
            ))

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus

    @on_event(GameEvent.CARD_ENTERS_PLAY, priority=TimingPriority.AFTER)
    def apply_bonus(self, ctx):
        """入场：+1生命值、+1神智值。"""
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        applied = ctx.game_state.scenario.vars.setdefault(_VARS_KEY, {})
        iid = ctx.target or self.instance_id
        if iid in applied:
            return
        applied[iid] = inv.investigator_id
        inv.health_bonus += 1
        inv.sanity_bonus += 1

    @on_event(GameEvent.CARD_LEAVES_PLAY, priority=TimingPriority.AFTER)
    def remove_bonus(self, ctx):
        """离场：移除+1/+1。"""
        applied = ctx.game_state.scenario.vars.get(_VARS_KEY, {})
        iid = ctx.target or self.instance_id
        owner_id = applied.pop(iid, None)
        if owner_id is None:
            return
        inv = ctx.game_state.get_investigator(owner_id)
        if inv is not None:
            inv.health_bonus -= 1
            inv.sanity_bonus -= 1
