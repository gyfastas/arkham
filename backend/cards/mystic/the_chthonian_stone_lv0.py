"""The Chthonian Stone (Level 0) — Mystic Asset, Hand slot, unique. (04030)
封印([skull]、[cultist]、[tablet]或[elder_thing])。
强制 - 在你在技能检定中揭示[auto_fail]标记后：将本卡返回手牌。

简化说明：
- 封印目标的官方选择（四种符号之一）简化为自动选择袋中第一个可用符号
  （优先 skull，其次 cultist/tablet/elder_thing）；袋中均无则不封印。
- 封印经 bind_chaos_bag 注入的混沌袋实现；返回手牌时封印标记归还袋中。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import ChaosTokenType, GameEvent, TimingPriority

_SEAL_CANDIDATES = [
    ChaosTokenType.SKULL, ChaosTokenType.CULTIST,
    ChaosTokenType.TABLET, ChaosTokenType.ELDER_THING,
]


class TheChthonianStone(CardImplementation):
    card_id = "the_chthonian_stone_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._bag = None
        self._sealed: list[ChaosTokenType] = []

    def bind_chaos_bag(self, chaos_bag) -> None:
        self._bag = chaos_bag

    @on_event(GameEvent.CARD_ENTERS_PLAY, priority=TimingPriority.AFTER)
    def seal_symbol_on_enter(self, ctx):
        """入场：封印袋中一个符号标记（自动选择，见 docstring）。"""
        if ctx.target != self.instance_id:
            return
        if self._bag is None:
            return
        for token in _SEAL_CANDIDATES:
            if self._bag.seal_token(token):
                self._sealed.append(token)
                ctx.game_state.log_effect(
                    f"🪨 钻地魔虫之石：封印 [{token.value}] 标记")
                return

    def _release_sealed(self) -> None:
        if self._bag is not None:
            for token in self._sealed:
                self._bag.release_token(token)
        self._sealed = []

    @on_event(GameEvent.CARD_LEAVES_PLAY, priority=TimingPriority.AFTER)
    def release_on_leave(self, ctx):
        if ctx.target != self.instance_id:
            return
        self._release_sealed()

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.FORCED)
    def return_to_hand_on_auto_fail(self, ctx):
        """强制：你揭示[auto_fail]后，将本卡返回手牌（封印标记归还袋中）。"""
        if ctx.chaos_token != ChaosTokenType.AUTO_FAIL:
            return
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None or inst.controller_id != ctx.investigator_id:
            return
        inv = ctx.game_state.get_investigator(inst.owner_id)
        if inv is None or self.instance_id not in inv.play_area:
            return

        from backend.engine.event_bus import EventContext

        self._release_sealed()
        ctx.game_state.cards_in_play.pop(self.instance_id, None)
        inv.play_area.remove(self.instance_id)
        mgr = getattr(ctx.game_state, "slot_managers", {}).get(inv.investigator_id)
        if mgr is not None:
            mgr.vacate(self.instance_id)
        inv.hand.append(self.card_id)
        bus = getattr(self, "_bus", None)
        if bus is not None:
            bus.emit(EventContext(
                game_state=ctx.game_state,
                event=GameEvent.CARD_LEAVES_PLAY,
                investigator_id=inv.investigator_id,
                target=self.instance_id,
                extra={"card_id": self.card_id},
            ))
        ctx.game_state.log_effect("🪨 钻地魔虫之石：揭示[auto_fail]，返回手牌")

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus
