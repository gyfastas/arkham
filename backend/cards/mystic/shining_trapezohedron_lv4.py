"""Shining Trapezohedron (Level 4) — Mystic Asset, Accessory slot, unique. (06329)
[reaction] 在你将要支付一张[[法术]]卡牌的费用时，消耗本卡：改为检定[willpower](X)，
X为该卡的资源费用。成功则其资源费用视为已支付；失败则取消打出该卡，不支付任何
费用（包括行动费用），且本轮剩余时间不能打出该卡名的卡牌。

简化/缺口说明：
- 引擎在 actions._play 中直接扣费，无"支付前"事件；实现以 RESOURCES_SPENT
  （扣费后、卡牌结算前发射）记录费用，再于该卡的 CARD_ENTERS_PLAY（资产）/
  CARD_PLAYED（事件）结算点介入：消耗本卡并回放一次意志(X)检定
  （CardSelfTest，无投入窗口）。
- 成功：返还资源费用（净效果=免费，视为本卡支付）。
- 失败（资产）：资产从场上弹回手牌、返还费用与行动（行动经
  perform_action 结算顺序抵消）。
- 失败（事件）：以 ctx.cancel() 取消事件效果、返还费用，并于随后的
  ACTION_PERFORMED 将事件从弃牌堆移回手牌（_play_event 无条件入弃牌堆，
  引擎缺口，以此近似"取消打出"）。
- "本轮不能再打出该卡名"：记录在 scenario.vars["trapezohedron_blocked"]，
  引擎无法阻止打出（缺口），供会话层查询。
"""

from backend.cards.base import on_event
from backend.cards.seeker._selftest import CardSelfTest
from backend.models.enums import GameEvent, Skill, TimingPriority


class ShiningTrapezohedron(CardSelfTest):
    card_id = "shining_trapezohedron_lv4"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        # (investigator_id, cost)：刚支付、等待卡牌结算的费用
        self._pending_payment: tuple[str, int] | None = None
        # 被取消、待从弃牌堆移回手牌的事件
        self._bounce_event: tuple[str, str] | None = None  # (inv_id, card_id)

    def _ready_for(self, game_state, investigator_id: str) -> bool:
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None or inst.exhausted:
            return False
        if inst.controller_id != investigator_id:
            return False
        inv = game_state.get_investigator(investigator_id)
        return inv is not None and self.instance_id in inv.play_area

    @on_event(GameEvent.RESOURCES_SPENT, priority=TimingPriority.WHEN)
    def track_payment(self, ctx):
        """记录打出流程中的费用支付（随后紧跟卡牌结算事件）。"""
        if not self._ready_for(ctx.game_state, ctx.investigator_id):
            return
        self._pending_payment = (ctx.investigator_id, int(ctx.amount or 0))

    @on_event(GameEvent.CARD_ENTERS_PLAY, priority=TimingPriority.WHEN)
    def on_asset_enters(self, ctx):
        if ctx.target == self.instance_id:
            self._pending_payment = None
            return
        card_id = ctx.extra.get("card_id")
        if not card_id:
            return
        self._resolve(ctx, card_id, is_event=False)

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def on_event_played(self, ctx):
        card_id = ctx.extra.get("card_id")
        if not card_id or card_id == self.card_id:
            return
        self._resolve(ctx, card_id, is_event=True)

    def _resolve(self, ctx, card_id: str, is_event: bool) -> None:
        pending = self._pending_payment
        self._pending_payment = None
        if pending is None:
            return
        inv_id, cost = pending
        if ctx.investigator_id != inv_id:
            return
        cd = ctx.game_state.get_card_data(card_id)
        if cd is None or "spell" not in (cd.traits or []):
            return
        if not self._ready_for(ctx.game_state, inv_id):
            return
        inv = ctx.game_state.get_investigator(inv_id)
        if inv is None:
            return

        inst = ctx.game_state.get_card_instance(self.instance_id)
        inst.exhausted = True
        result = self.run_self_test(
            ctx.game_state, inv_id, Skill.WILLPOWER, cost,
            source=self.instance_id,
        )
        if result is None:
            return
        success, _margin = result
        name = ctx.game_state.card_name(card_id)
        if success:
            # 费用视为已由本卡支付：返还资源
            inv.resources += cost
            ctx.extra["trapezohedron_paid"] = card_id
            ctx.game_state.log_effect(
                f"🔮 闪耀的偏方三八面体：意志检定成功，【{name}】费用视为已支付")
            return

        # 失败：取消打出，不支付任何费用（含行动费用）
        ctx.extra["trapezohedron_cancelled"] = card_id
        inv.resources += cost
        inv.actions_remaining += 1  # 行动费用取消（perform_action 随后扣回）
        blocked = ctx.game_state.scenario.vars.setdefault(
            "trapezohedron_blocked", [])
        if card_id not in blocked:
            blocked.append(card_id)
        ctx.game_state.log_effect(
            f"🔮 闪耀的偏方三八面体：意志检定失败，取消打出【{name}】")
        if is_event:
            # 取消事件效果；弃牌堆回手在 ACTION_PERFORMED 处理
            ctx.cancel()
            self._bounce_event = (inv_id, card_id)
        else:
            # 资产：从场上弹回手牌
            target_iid = ctx.target
            entering = ctx.game_state.cards_in_play.pop(target_iid, None)
            if entering is not None:
                if target_iid in inv.play_area:
                    inv.play_area.remove(target_iid)
                mgr = getattr(ctx.game_state, "slot_managers", {}).get(inv_id)
                if mgr is not None:
                    mgr.vacate(target_iid)
                inv.hand.append(card_id)
                bus = getattr(self, "_selftest_bus", None)
                if bus is not None:
                    from backend.engine.event_bus import EventContext
                    bus.emit(EventContext(
                        game_state=ctx.game_state,
                        event=GameEvent.CARD_LEAVES_PLAY,
                        investigator_id=inv_id,
                        target=target_iid,
                        extra={"card_id": card_id},
                    ))

    @on_event(GameEvent.ACTION_PERFORMED, priority=TimingPriority.AFTER)
    def bounce_cancelled_event(self, ctx):
        """将被取消的事件从弃牌堆移回手牌（近似"取消打出"）。"""
        if self._bounce_event is None:
            return
        inv_id, card_id = self._bounce_event
        self._bounce_event = None
        inv = ctx.game_state.get_investigator(inv_id)
        if inv is not None and card_id in inv.discard:
            inv.discard.remove(card_id)
            inv.hand.append(card_id)

    @on_event(GameEvent.ROUND_ENDS, priority=TimingPriority.AFTER)
    def clear_round_flags(self, ctx):
        self._pending_payment = None
        self._bounce_event = None
        ctx.game_state.scenario.vars.pop("trapezohedron_blocked", None)
