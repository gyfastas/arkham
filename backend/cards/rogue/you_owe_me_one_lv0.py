"""You owe me one! (Level 0) — Rogue Event. (05319)
查看另一位调查员的手牌。你可以打出该调查员手牌中的一张非弱点卡牌，
置于你的控制之下。如果你这么做，你和该调查员每人抽取1张卡牌。

简化说明：
- 目标调查员/卡牌选择需会话层传参：ctx.extra["target_investigator"] 指定
  目标调查员，ctx.extra["play_card_id"] 指定打出的卡；缺省时自动选择
  第一位其他调查员手牌中第一张可负担的非弱点支援/事件（官方为玩家自选）。
- "查看手牌"无隐私通道：结果被放入 ctx.extra["you_owe_me_one_looked"]，
  供会话层展示给打出者。
- 打出需支付该卡费用（官方FAQ：由"You owe me one!"的打出者支付）。
- 支援卡置于你的控制之下（controller=你），所有权保留原调查员（owner
  不变，离场时回其弃牌堆）；事件结算后进入原持有者的弃牌堆。
- 技能卡无法被"打出"，不参与自动选择；显式指定弱点/技能/负担不起的卡
  则效果落空（不抽牌）。
- 引擎缺口：卡牌代码访问不到 CardRegistry，经本卡入场的支援不会自动注册
  卡面能力（同 ever_vigilant / a_chance_encounter）；事件通过嵌套
  CARD_PLAYED 分发，已注册的实现可正常响应，未注册的临时实现注册
  需会话层接线（见报告）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import CardType, GameEvent, TimingPriority
from backend.models.state import CardInstance, is_weakness_card


class YouOweMeOne(CardImplementation):
    card_id = "you_owe_me_one_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._bus = None

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus  # 放置入场/嵌套事件需经事件总线发出

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def play_from_other_hand(self, ctx):
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return

        # 目标：另一位调查员（显式指定或自动取第一位其他调查员）
        target = None
        target_id = ctx.extra.get("target_investigator")
        if target_id is not None:
            candidate = ctx.game_state.get_investigator(target_id)
            if candidate is not None \
                    and candidate.investigator_id != inv.investigator_id:
                target = candidate
        else:
            target = next(
                (o for o in ctx.game_state.investigators.values()
                 if o.investigator_id != inv.investigator_id),
                None,
            )
        if target is None:
            return  # 单人局无合法目标，效果落空

        # 查看其手牌（供会话层展示；自动选择直接据此进行）
        ctx.extra["you_owe_me_one_looked"] = list(target.hand)

        def _playable(card_id: str) -> bool:
            cd = ctx.game_state.get_card_data(card_id)
            if cd is None or is_weakness_card(cd):
                return False
            if cd.type not in (CardType.ASSET, CardType.EVENT):
                return False
            if inv.resources < (cd.cost or 0):
                return False
            if cd.type == CardType.ASSET and cd.slots:
                slot_mgr = getattr(ctx.game_state, "slot_managers", {}).get(
                    inv.investigator_id)
                if slot_mgr is not None \
                        and not slot_mgr.can_play_card(cd.slots, cd.traits):
                    return False
            return True

        chosen = ctx.extra.get("play_card_id")
        if chosen is not None:
            if chosen not in target.hand or not _playable(chosen):
                return
        else:
            chosen = next((cid for cid in target.hand if _playable(cid)), None)
            if chosen is None:
                return

        card_data = ctx.game_state.get_card_data(chosen)
        inv.resources -= (card_data.cost or 0)
        target.hand.remove(chosen)

        if card_data.type == CardType.ASSET:
            # 放置入场，置于你的控制之下（复刻 _play_asset；所有权不变）
            instance_id = ctx.game_state.next_instance_id()
            inst = CardInstance(
                instance_id=instance_id,
                card_id=chosen,
                owner_id=target.investigator_id,
                controller_id=inv.investigator_id,
                slot_used=list(card_data.slots or []),
            )
            if card_data.uses:
                inst.uses = dict(card_data.uses)
            ctx.game_state.cards_in_play[instance_id] = inst
            inv.play_area.append(instance_id)
            slot_mgr = getattr(ctx.game_state, "slot_managers", {}).get(
                inv.investigator_id)
            if slot_mgr is not None and card_data.slots:
                slot_mgr.occupy(instance_id, card_data.slots, card_data.traits)
            if self._bus is not None:
                from backend.engine.event_bus import EventContext
                self._bus.emit(EventContext(
                    game_state=ctx.game_state,
                    event=GameEvent.CARD_ENTERS_PLAY,
                    investigator_id=inv.investigator_id,
                    target=instance_id,
                    extra={"card_id": chosen},
                ))
        else:
            # 事件：结算后进原持有者的弃牌堆；经嵌套 CARD_PLAYED 分发效果
            target.discard.append(chosen)
            if self._bus is not None:
                from backend.engine.event_bus import EventContext
                self._bus.emit(EventContext(
                    game_state=ctx.game_state,
                    event=GameEvent.CARD_PLAYED,
                    investigator_id=inv.investigator_id,
                    extra={
                        "card_id": chosen,
                        "played_from_hand_of": target.investigator_id,
                    },
                ))

        # 双方各抽1张
        for drawer in (inv, target):
            if drawer.deck:
                drawer.hand.append(drawer.deck.pop(0))

        ctx.extra["you_owe_me_one_played"] = chosen
        ctx.game_state.log_effect(
            f"🤝 你欠我一次：打出{ctx.game_state.card_name(target.investigator_id)}"
            f"手牌中的【{ctx.game_state.card_name(chosen)}】，双方各抽1张")
