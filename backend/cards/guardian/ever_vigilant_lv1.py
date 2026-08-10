"""Ever Vigilant (Level 1) — Guardian Event. (03023)
每次1张，打出你手牌中最多3张支援卡，每张资源费用减少1点。

简化说明：
- 目标选择简化为自动：按费用从高到低依次打出可负担的至多3张支援
  （官方为玩家自选，通常优先高费卡）。
- 费用减少1点（最低0）；槽位不足时跳过该卡（完整槽位冲突流程需 UI，
  见 engine/actions 的 slot conflict 通道）。
- 引擎缺口：卡牌代码无法访问 CardRegistry，经本卡入场的支援不会自动注册
  卡面能力（会话层可对 ctx.extra["ever_vigilant_played"] 中的实例补注册，
  见报告）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import CardType, GameEvent, TimingPriority
from backend.models.state import CardInstance


class EverVigilant(CardImplementation):
    card_id = "ever_vigilant_lv1"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._bus = None

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def play_assets(self, ctx):
        """打出时：从手牌依次打出至多3张支援卡，各减1费。"""
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return

        # 候选：手牌中的支援卡，按费用从高到低（自动选择的简化）
        candidates = []
        for card_id in inv.hand:
            data = ctx.game_state.get_card_data(card_id)
            if data is not None and data.type == CardType.ASSET:
                candidates.append((data.cost or 0, card_id))
        candidates.sort(reverse=True)

        slot_mgr = getattr(ctx.game_state, "slot_managers", {}).get(inv.investigator_id)
        played = []
        for _, card_id in candidates:
            if len(played) >= 3:
                break
            data = ctx.game_state.get_card_data(card_id)
            cost = max(0, (data.cost or 0) - 1)
            if inv.resources < cost:
                continue
            if data.slots and slot_mgr is not None \
                    and not slot_mgr.can_play_card(data.slots, data.traits):
                ctx.game_state.log_effect(
                    f"👀 时刻警惕：槽位不足，跳过【{ctx.game_state.card_name(card_id)}】")
                continue

            inv.resources -= cost
            inv.hand.remove(card_id)
            instance_id = ctx.game_state.next_instance_id()
            instance = CardInstance(
                instance_id=instance_id,
                card_id=card_id,
                owner_id=inv.investigator_id,
                controller_id=inv.investigator_id,
                slot_used=list(data.slots),
            )
            if data.uses:
                instance.uses = dict(data.uses)
            ctx.game_state.cards_in_play[instance_id] = instance
            inv.play_area.append(instance_id)
            if data.slots and slot_mgr is not None:
                slot_mgr.occupy(instance_id, data.slots, data.traits)
            played.append(instance_id)
            ctx.game_state.log_effect(
                f"👀 时刻警惕：减1费打出【{ctx.game_state.card_name(card_id)}】")
            if self._bus is not None:
                from backend.engine.event_bus import EventContext
                self._bus.emit(EventContext(
                    game_state=ctx.game_state,
                    event=GameEvent.CARD_ENTERS_PLAY,
                    investigator_id=inv.investigator_id,
                    target=instance_id,
                    extra={"card_id": card_id},
                ))

        ctx.extra["ever_vigilant_played"] = played
