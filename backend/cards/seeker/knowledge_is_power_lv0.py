"""Knowledge is Power (Level 0) — Seeker Event, Fast. (05231)
快速。只能在你回合中打出。
选择你控制的一张[[书籍]]或[[法术]]支援卡，或揭示你手牌里的一张[[书籍]]
或[[法术]]支援卡。结算该支援卡上的一项[action]或[free]能力，忽略所有
费用（包括其[action]费用）。然后，如果该支援卡是从你的手牌里揭示的，
你可以将其丢弃来抽取1张卡牌。

简化说明：
- 目标默认为你场上第一张带 activations 的书籍/法术支援卡；可用
  ctx.extra["asset_instance_id"]（场上）或 ctx.extra["hand_card_id"]
  （手牌揭示）指定；结算的能力为该卡 activations 的第一项；
- "忽略所有费用"实现为：快照目标的 uses/exhausted，调用其激活方法后
  恢复（行动费用由本卡直接调用方法、不经会话层扣行动而天然忽略）；
- 手牌揭示：临时放入场上（建实例、不占槽）结算后取回手牌；随后
  "你可以丢弃来抽1张"默认不丢弃，可用 ctx.extra["discard_revealed"]=True
  选择丢弃抽牌；
- 已知限制（引擎缺口）：卡实现拿不到 CardRegistry 的活动实例，故为
  目标卡新建未注册的实现实例来调用——arm 型能力（flashlight、
  shrivelling 等"武装后等下一次行动"）的武装状态会随临时实例丢失，
  仅自洽型 activate（old_book_of_lore、medical_texts 等）可完整结算；
- "只能在你回合中打出"的时机校验由会话层负责。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import CardType, GameEvent, TimingPriority
from backend.models.state import CardInstance


class KnowledgeIsPower(CardImplementation):
    card_id = "knowledge_is_power_lv0"

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus

    def bind_chaos_bag(self, chaos_bag) -> None:
        self._bag = chaos_bag

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def resolve_tome_or_spell(self, ctx):
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return

        hand_card_id = ctx.extra.get("hand_card_id")
        if hand_card_id is not None:
            self._resolve_from_hand(ctx, inv, hand_card_id)
            return

        instance_id = ctx.extra.get("asset_instance_id") or self._auto_target(ctx, inv)
        if instance_id is None:
            ctx.game_state.log_effect("📖 知识就是力量：没有可用的书籍/法术支援卡")
            return
        self._resolve_on_instance(ctx, inv, instance_id)

    # ------------------------------------------------ 内部
    def _auto_target(self, ctx, inv) -> str | None:
        """你控制的第一张带 activations 的书籍/法术支援卡。"""
        for iid in inv.play_area:
            if not self._is_tome_or_spell(ctx, instance_id=iid):
                continue
            inst = ctx.game_state.get_card_instance(iid)
            cls = self._impl_class(inst.card_id) if inst else None
            if cls is not None and getattr(cls, "activations", None):
                return iid
        return None

    def _is_tome_or_spell(self, ctx, instance_id=None, card_id=None) -> bool:
        if card_id is None and instance_id is not None:
            inst = ctx.game_state.get_card_instance(instance_id)
            card_id = inst.card_id if inst else None
        cd = ctx.game_state.get_card_data(card_id) if card_id else None
        if cd is None or cd.type != CardType.ASSET:
            return False
        traits = [t.lower() for t in (cd.traits or [])]
        return "tome" in traits or "spell" in traits

    @staticmethod
    def _impl_class(card_id: str):
        from backend.cards.registry import CardRegistry
        registry = CardRegistry()
        registry.discover_cards()
        return registry.get_implementation(card_id)

    def _make_impl(self, card_id: str, instance_id: str):
        """为目标卡建一个未注册的实现实例，并尽力接线自检总线/混沌袋。"""
        cls = self._impl_class(card_id)
        if cls is None:
            return None
        impl = cls(instance_id)
        bus = getattr(self, "_bus", None)
        bag = getattr(self, "_bag", None)
        if bus is not None and hasattr(impl, "_selftest_bus"):
            impl._selftest_bus = bus
        if bag is not None and hasattr(impl, "bind_chaos_bag"):
            impl.bind_chaos_bag(bag)
        return impl

    def _call_first_activation(self, impl, game_state, investigator_id) -> bool:
        activations = getattr(impl, "activations", None) or []
        if not activations:
            return False
        method = getattr(impl, activations[0]["method"], None)
        if method is None:
            return False
        return bool(method(game_state, investigator_id))

    def _resolve_on_instance(self, ctx, inv, instance_id: str) -> None:
        if instance_id not in inv.play_area:
            return
        if not self._is_tome_or_spell(ctx, instance_id=instance_id):
            return
        inst = ctx.game_state.get_card_instance(instance_id)
        impl = self._make_impl(inst.card_id, instance_id) if inst else None
        if impl is None:
            return

        # 忽略所有费用：快照 uses/exhausted，结算后恢复
        saved_uses = dict(inst.uses)
        saved_exhausted = inst.exhausted
        ok = self._call_first_activation(impl, ctx.game_state, inv.investigator_id)
        inst.uses.clear()
        inst.uses.update(saved_uses)
        inst.exhausted = saved_exhausted
        if ok:
            ctx.extra["knowledge_is_power_resolved"] = inst.card_id
            ctx.game_state.log_effect(
                f"📖 知识就是力量：忽略费用结算【{ctx.game_state.card_name(inst.card_id)}】的能力"
            )

    def _resolve_from_hand(self, ctx, inv, hand_card_id: str) -> None:
        if hand_card_id not in inv.hand:
            return
        if not self._is_tome_or_spell(ctx, card_id=hand_card_id):
            return
        cd = ctx.game_state.get_card_data(hand_card_id)
        impl = self._make_impl(hand_card_id, f"kip_temp_{hand_card_id}")
        if impl is None:
            return

        # 揭示手牌结算：临时放入场上（不占槽），结算后取回
        temp_id = impl.instance_id
        temp_inst = CardInstance(
            instance_id=temp_id,
            card_id=hand_card_id,
            owner_id=inv.investigator_id,
            controller_id=inv.investigator_id,
        )
        if cd.uses:
            temp_inst.uses = dict(cd.uses)
        ctx.game_state.cards_in_play[temp_id] = temp_inst
        inv.play_area.append(temp_id)
        try:
            ok = self._call_first_activation(impl, ctx.game_state, inv.investigator_id)
        finally:
            if temp_id in inv.play_area:
                inv.play_area.remove(temp_id)
            ctx.game_state.cards_in_play.pop(temp_id, None)
        if not ok:
            return
        ctx.extra["knowledge_is_power_resolved"] = hand_card_id
        ctx.game_state.log_effect(
            f"📖 知识就是力量：揭示手牌【{ctx.game_state.card_name(hand_card_id)}】，"
            "忽略费用结算其能力"
        )

        # 然后：你可以将其丢弃来抽取1张卡牌（默认不丢弃）
        if ctx.extra.get("discard_revealed") and hand_card_id in inv.hand:
            inv.hand.remove(hand_card_id)
            inv.discard.append(hand_card_id)
            if inv.deck:
                inv.hand.append(inv.deck.pop(0))
            ctx.extra["knowledge_is_power_discarded"] = hand_card_id
