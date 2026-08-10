"""Ghastly Revelation (Level 0) — Seeker Event. (05275)
发现你所在地点的3个线索。将你任意数量的线索交给其他一位调查员，或将
你任意数量的线索放置在任意一个地点上。你被击败并受到1点精神创伤。
本行动不会引起趁乱攻击。

简化说明：
- 线索分配默认保留在自己手中（"任意数量"含0）；可用
  ctx.extra["give_clues_to"]（其他调查员 id）+ ctx.extra["clue_count"]
  或 ctx.extra["place_on_location"] + ctx.extra["clue_count"] 显式分配
  （在击败结算前移交）；
- 地点线索不足3个时只发现剩余数量（与引擎调查行动一致）；
- "你被击败"实现为将已受恐惧设为神智上限（is_defeated 成立）并发出
  INVESTIGATOR_DEFEATED；1点精神创伤记录在 investigator_card
  （无 investigator_card 时记录在状态对象上，与 ill_see_you_in_hell 一致）；
- 不引起趁乱攻击：一次性豁免标记取消随后的 ATTACK_OF_OPPORTUNITY。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class GhastlyRevelation(CardImplementation):
    card_id = "ghastly_revelation_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._bus = None
        self._aoo_free: str | None = None

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def reveal_and_be_defeated(self, ctx):
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return

        # 发现你所在地点的3个线索
        location = ctx.game_state.get_location(inv.location_id)
        found = 0
        if location is not None:
            found = min(3, location.clues)
            location.clues -= found
            inv.clues += found
        ctx.extra["ghastly_revelation_clues"] = found
        if found:
            ctx.game_state.log_effect(f"👻 骇人启示：发现{found}个线索")
            if self._bus is not None:
                from backend.engine.event_bus import EventContext
                self._bus.emit(EventContext(
                    game_state=ctx.game_state,
                    event=GameEvent.CLUE_DISCOVERED,
                    investigator_id=inv.investigator_id,
                    location_id=inv.location_id,
                    amount=found,
                    source=self.instance_id,
                ))

        # 线索再分配（默认保留；显式参数时先移交再击败）
        self._redistribute(ctx, inv)

        # 你被击败并受到1点精神创伤
        inv.horror = inv.sanity
        inv_card = inv.investigator_card
        if inv_card is not None:
            inv_card.mental_trauma = getattr(inv_card, "mental_trauma", 0) + 1
        else:
            inv.mental_trauma = getattr(inv, "mental_trauma", 0) + 1
        ctx.extra["ghastly_revelation_defeated"] = True
        ctx.game_state.log_effect("👻 骇人启示：你被击败，承受1点精神创伤")
        if self._bus is not None:
            from backend.engine.event_bus import EventContext
            self._bus.emit(EventContext(
                game_state=ctx.game_state,
                event=GameEvent.INVESTIGATOR_DEFEATED,
                investigator_id=inv.investigator_id,
            ))

        # 本行动不引起趁乱攻击
        self._aoo_free = inv.investigator_id

    def _redistribute(self, ctx, inv) -> None:
        count = int(ctx.extra.get("clue_count") or 0)
        if count <= 0:
            return
        count = min(count, inv.clues)
        give_to = ctx.extra.get("give_clues_to")
        if give_to:
            other = ctx.game_state.get_investigator(give_to)
            if other is not None and other.investigator_id != inv.investigator_id:
                inv.clues -= count
                other.clues += count
                ctx.extra["ghastly_revelation_given"] = (give_to, count)
                return
        place_on = ctx.extra.get("place_on_location")
        if place_on:
            loc = ctx.game_state.get_location(place_on)
            if loc is not None:
                inv.clues -= count
                loc.clues += count
                ctx.extra["ghastly_revelation_placed"] = (place_on, count)

    @on_event(GameEvent.ATTACK_OF_OPPORTUNITY, priority=TimingPriority.WHEN)
    def cancel_aoo(self, ctx):
        if self._aoo_free is not None and ctx.investigator_id == self._aoo_free:
            ctx.cancel()

    @on_event(GameEvent.ACTION_PERFORMED, priority=TimingPriority.AFTER)
    def clear_aoo(self, ctx):
        self._aoo_free = None
